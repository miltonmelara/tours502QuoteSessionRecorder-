"""Event timeline widget — scrolling list of captured browser events."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.schemas.event_schema import BrowserEvent, EventType

_TYPE_ICONS: dict[str, str] = {
    EventType.page_navigated: "🌐",
    EventType.click: "🖱",
    EventType.input: "⌨",
    EventType.search_submitted: "🔍",
    EventType.screenshot_manual: "📷",
    EventType.screenshot_auto: "📸",
    EventType.session_started: "▶",
    EventType.session_finished: "⏹",
    EventType.recording_paused: "⏸",
    EventType.recording_resumed: "▶",
}


class EventTimelineWidget(QWidget):
    """Displays a live list of browser events recorded during the session."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Event Timeline")
        inner = QVBoxLayout(box)

        self._list = QListWidget()
        self._list.setWordWrap(False)
        inner.addWidget(self._list)

        outer.addWidget(box)

    def append_event(self, event: BrowserEvent) -> None:
        """Add a row to the timeline for the given event."""
        icon = _TYPE_ICONS.get(event.event_type, "•")
        ts = event.timestamp[11:19] if event.timestamp else ""  # HH:MM:SS portion

        if event.event_type == EventType.page_navigated:
            desc = f"{event.url or ''}"
        elif event.event_type == EventType.click:
            tag = event.element_tag or ""
            text = event.element_text or ""
            desc = f"<{tag}> {text[:60]}" if text else f"<{tag}>"
        elif event.event_type in (EventType.input, EventType.search_submitted):
            val = event.input_value or ""
            desc = f"[{event.input_name or 'field'}] = {val[:60]}" if not event.redacted else "[REDACTED]"
        elif event.event_type in (EventType.screenshot_manual, EventType.screenshot_auto):
            desc = event.screenshot_path or ""
        else:
            desc = event.event_type.value

        row = f"{ts}  {icon} {event.event_type.value:<22}  {desc}"
        item = QListWidgetItem(row)
        self._list.addItem(item)
        self._list.scrollToBottom()

    def clear_timeline(self) -> None:
        self._list.clear()
