"""Browser status panel widget."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class BrowserStatusWidget(QWidget):
    """Displays live browser and session stats."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._elapsed_seconds: int = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Browser Status")
        form = QFormLayout(box)

        self._url_label = QLabel("—")
        self._url_label.setWordWrap(True)
        self._title_label = QLabel("—")
        self._title_label.setWordWrap(True)
        self._events_label = QLabel("0")
        self._screenshots_label = QLabel("0")
        self._duration_label = QLabel("00:00:00")
        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("font-weight: bold; color: gray;")

        form.addRow("Status:", self._status_label)
        form.addRow("Current URL:", self._url_label)
        form.addRow("Page Title:", self._title_label)
        form.addRow("Events captured:", self._events_label)
        form.addRow("Screenshots:", self._screenshots_label)
        form.addRow("Session duration:", self._duration_label)

        outer.addWidget(box)

    # ------------------------------------------------------------------
    # Public update methods (called from MainWindow)
    # ------------------------------------------------------------------

    def update_url(self, url: str) -> None:
        self._url_label.setText(url or "—")

    def update_title(self, title: str) -> None:
        self._title_label.setText(title or "—")

    def update_event_count(self, count: int) -> None:
        self._events_label.setText(str(count))

    def update_screenshot_count(self, count: int) -> None:
        self._screenshots_label.setText(str(count))

    def set_status(self, text: str, color: str = "gray") -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"font-weight: bold; color: {color};")

    # ------------------------------------------------------------------
    # Timer control
    # ------------------------------------------------------------------

    def start_timer(self) -> None:
        self._elapsed_seconds = 0
        self._timer.start(1000)

    def stop_timer(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._elapsed_seconds += 1
        h = self._elapsed_seconds // 3600
        m = (self._elapsed_seconds % 3600) // 60
        s = self._elapsed_seconds % 60
        self._duration_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
