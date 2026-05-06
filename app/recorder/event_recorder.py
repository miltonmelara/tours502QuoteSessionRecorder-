"""Event recorder: receives raw browser callbacks and builds BrowserEvent objects.

This module is the redaction gate.  Every piece of user-typed data passes
through :func:`redact_sensitive_value` before it is stored.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from app.schemas.event_schema import BrowserEvent, EventType
from app.storage.session_store import SessionStore
from app.utils.sanitization import redact_sensitive_value
from app.utils.time_utils import now_iso

logger = logging.getLogger(__name__)

# Callback type: (event: BrowserEvent) -> None
EventCallback = Callable[[BrowserEvent], None]


class EventRecorder:
    """Accepts browser-event payloads and persists them to :class:`SessionStore`.

    Set :attr:`is_paused` to ``True`` to stop recording without stopping the
    browser; all incoming callbacks are silently discarded while paused.
    """

    def __init__(
        self,
        session_id: str,
        session_store: SessionStore,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self._session_id = session_id
        self._store = session_store
        self._on_event = on_event  # UI callback for live timeline updates
        self.is_paused: bool = False

    # ------------------------------------------------------------------
    # Public recording methods (called by BrowserController)
    # ------------------------------------------------------------------

    def record_navigation(
        self,
        url: str,
        title: str,
        screenshot_path: Optional[Path] = None,
    ) -> BrowserEvent:
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=EventType.page_navigated,
            url=url,
            domain=self._extract_domain(url),
            page_title=title,
            screenshot_path=self._rel(screenshot_path),
        )
        return self._persist(event)

    def record_click(
        self,
        url: str,
        title: str,
        selector: Optional[str] = None,
        element_text: Optional[str] = None,
        element_tag: Optional[str] = None,
        coordinates: Optional[dict] = None,
        screenshot_path: Optional[Path] = None,
    ) -> BrowserEvent:
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=EventType.click,
            url=url,
            domain=self._extract_domain(url),
            page_title=title,
            selector=selector,
            element_text=element_text[:200] if element_text else None,
            element_tag=element_tag,
            coordinates=coordinates,
            screenshot_path=self._rel(screenshot_path),
        )
        return self._persist(event)

    def record_input(
        self,
        url: str,
        title: str,
        value: str,
        input_type: str = "text",
        input_name: str = "",
        field_id: str = "",
        field_placeholder: str = "",
        selector: Optional[str] = None,
        screenshot_path: Optional[Path] = None,
    ) -> BrowserEvent:
        stored_value, was_redacted = redact_sensitive_value(
            value,
            input_type=input_type,
            field_name=input_name,
            field_id=field_id,
            field_placeholder=field_placeholder,
        )
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=EventType.input,
            url=url,
            domain=self._extract_domain(url),
            page_title=title,
            selector=selector,
            input_value=stored_value,
            input_type=input_type,
            input_name=input_name or None,
            redacted=was_redacted,
            screenshot_path=self._rel(screenshot_path),
        )
        return self._persist(event)

    def record_search(
        self,
        url: str,
        title: str,
        query: str,
        form_selector: Optional[str] = None,
        screenshot_path: Optional[Path] = None,
    ) -> BrowserEvent:
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=EventType.search_submitted,
            url=url,
            domain=self._extract_domain(url),
            page_title=title,
            input_value=query,
            selector=form_selector,
            screenshot_path=self._rel(screenshot_path),
        )
        return self._persist(event)

    def record_screenshot(
        self,
        url: str,
        title: str,
        screenshot_path: Path,
        manual: bool = True,
    ) -> BrowserEvent:
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=EventType.screenshot_manual if manual else EventType.screenshot_auto,
            url=url,
            domain=self._extract_domain(url),
            page_title=title,
            screenshot_path=self._rel(screenshot_path),
        )
        return self._persist(event)

    def record_system(self, event_type: EventType) -> BrowserEvent:
        """Record a session-lifecycle event (started, finished, paused, resumed)."""
        event = BrowserEvent(
            session_id=self._session_id,
            timestamp=now_iso(),
            event_type=event_type,
        )
        return self._persist(event, bypass_pause=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _persist(self, event: BrowserEvent, bypass_pause: bool = False) -> BrowserEvent:
        if self.is_paused and not bypass_pause:
            logger.debug("Recording paused — discarding event %s", event.event_type)
            return event
        self._store.add_event(event)
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                logger.warning("on_event callback raised", exc_info=True)
        return event

    @staticmethod
    def _extract_domain(url: str) -> Optional[str]:
        try:
            return urlparse(url).netloc or None
        except Exception:
            return None

    @staticmethod
    def _rel(path: Optional[Path]) -> Optional[str]:
        """Convert an absolute screenshot path to a relative string for JSON."""
        if path is None:
            return None
        return str(path.name)  # store just the filename; ZipExporter uses full paths
