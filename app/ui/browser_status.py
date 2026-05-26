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
        self._clicks_label = QLabel("0")
        self._inputs_label = QLabel("0")
        self._searches_label = QLabel("0")
        self._scrolls_label = QLabel("0")
        self._virtual_nav_label = QLabel("0")
        self._ui_changes_label = QLabel("0")
        self._screenshots_label = QLabel("0")
        self._duration_label = QLabel("00:00:00")
        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("font-weight: bold; color: gray;")

        form.addRow("Status:", self._status_label)
        form.addRow("Current URL:", self._url_label)
        form.addRow("Page Title:", self._title_label)
        form.addRow("Events captured:", self._events_label)
        form.addRow("Clicks:", self._clicks_label)
        form.addRow("Inputs:", self._inputs_label)
        form.addRow("Searches:", self._searches_label)
        form.addRow("Scrolls:", self._scrolls_label)
        form.addRow("Virtual nav:", self._virtual_nav_label)
        form.addRow("UI changes:", self._ui_changes_label)
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

    def current_url(self) -> str:
        text = self._url_label.text().strip()
        return "" if text == "—" else text

    def current_title(self) -> str:
        text = self._title_label.text().strip()
        return "" if text == "—" else text

    def update_event_count(self, count: int) -> None:
        self._events_label.setText(str(count))

    def update_event_breakdown(
        self,
        *,
        clicks: int,
        inputs: int,
        searches: int,
        scrolls: int,
        virtual_nav: int,
        ui_changes: int,
    ) -> None:
        self._clicks_label.setText(str(clicks))
        self._inputs_label.setText(str(inputs))
        self._searches_label.setText(str(searches))
        self._scrolls_label.setText(str(scrolls))
        self._virtual_nav_label.setText(str(virtual_nav))
        self._ui_changes_label.setText(str(ui_changes))

    def reset_event_breakdown(self) -> None:
        self.update_event_breakdown(
            clicks=0,
            inputs=0,
            searches=0,
            scrolls=0,
            virtual_nav=0,
            ui_changes=0,
        )

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
