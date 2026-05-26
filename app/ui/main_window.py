"""Main application window.

Orchestrates all widgets, recorder services, and export logic.
"""

from __future__ import annotations

import atexit
import logging
import os
import platform
import queue
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_VERSION
from app.export.zip_exporter import ZipExporter
from app.recorder.browser_controller import BrowserController
from app.recorder.event_recorder import EventRecorder
from app.recorder.screenshot_service import ScreenshotService
from app.recorder.snapshot_service import SnapshotService
from app.schemas.event_schema import BrowserEvent, EventType
from app.schemas.note_schema import NoteType, ReasoningNote
from app.schemas.session_schema import SessionRecord
from app.storage.file_store import FileStore
from app.storage.session_store import SessionStore
from app.ui.browser_status import BrowserStatusWidget
from app.ui.decision_dialog import DecisionDialog
from app.ui.event_timeline import EventTimelineWidget
from app.ui.notes_panel import NotesPanelWidget
from app.ui.session_form import SessionFormWidget
from app.utils.paths import session_folder_path
from app.utils.time_utils import now_iso, session_timestamp

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Central coordinator of the Tours502 Quote Session Recorder."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Tours502 Quote Session Recorder  v{APP_VERSION}")
        self.setMinimumSize(1100, 780)

        # Thread-safe queue: Playwright thread pushes events; Qt timer drains it
        self._event_queue: queue.Queue = queue.Queue()
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(100)  # drain every 100 ms
        self._drain_timer.timeout.connect(self._drain_event_queue)
        self._drain_timer.start()

        # Session state
        self._session_record: Optional[SessionRecord] = None
        self._session_folder: Optional[Path] = None
        self._session_ts: Optional[str] = None
        self._file_store: Optional[FileStore] = None
        self._session_store: Optional[SessionStore] = None
        self._event_recorder: Optional[EventRecorder] = None
        self._screenshot_service: Optional[ScreenshotService] = None
        self._snapshot_service: Optional[SnapshotService] = None
        self._browser_controller: Optional[BrowserController] = None
        self._zip_path: Optional[Path] = None
        self._event_breakdown = {
            "clicks": 0,
            "inputs": 0,
            "searches": 0,
            "scrolls": 0,
            "virtual_nav": 0,
            "ui_changes": 0,
        }

        self._build_ui()
        self._set_idle_state()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)

        # Privacy warning banner
        root.addWidget(self._make_privacy_banner())

        # Toolbar
        self._make_toolbar()

        # Main content: left column | right column
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left column ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)

        self._session_form = SessionFormWidget()
        left_layout.addWidget(self._session_form)

        self._browser_status = BrowserStatusWidget()
        left_layout.addWidget(self._browser_status)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # --- Right column ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self._notes_panel = NotesPanelWidget()
        self._notes_panel.note_submitted.connect(self._on_note_submitted)
        right_layout.addWidget(self._notes_panel)

        self._timeline = EventTimelineWidget()
        right_layout.addWidget(self._timeline)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)

        root.addWidget(splitter, 1)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready — fill in session details and click Start Recording.")

    def _make_privacy_banner(self) -> QWidget:
        banner = QLabel(
            "⚠  PRIVACY REMINDER:  Do NOT enter payment information, passwords, "
            "or sensitive personal documents during recorded sessions "
            "unless recording is paused first."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background: #fff3cd; color: #856404; border: 1px solid #ffc107; "
            "padding: 6px 10px; border-radius: 4px; font-size: 12px;"
        )
        return banner

    def _make_toolbar(self) -> None:
        tb = QToolBar("Recording Controls")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._btn_start = QPushButton("▶  Start Recording")
        self._btn_start.setStyleSheet("QPushButton { background: #198754; color: white; padding: 5px 12px; border-radius: 4px; }")
        self._btn_start.clicked.connect(self._on_start_recording)

        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._on_pause_recording)

        self._btn_resume = QPushButton("▶  Resume")
        self._btn_resume.setEnabled(False)
        self._btn_resume.clicked.connect(self._on_resume_recording)

        self._btn_screenshot = QPushButton("📷  Screenshot")
        self._btn_screenshot.setEnabled(False)
        self._btn_screenshot.clicked.connect(self._on_manual_screenshot)

        self._btn_decision = QPushButton("⚖  Add Decision")
        self._btn_decision.setEnabled(False)
        self._btn_decision.clicked.connect(self._on_add_decision)

        self._btn_finish = QPushButton("⏹  Finish Recording")
        self._btn_finish.setStyleSheet("QPushButton { background: #dc3545; color: white; padding: 5px 12px; border-radius: 4px; }")
        self._btn_finish.setEnabled(False)
        self._btn_finish.clicked.connect(self._on_finish_recording)

        self._btn_generate_zip = QPushButton("🗜  Generate ZIP")
        self._btn_generate_zip.setEnabled(False)
        self._btn_generate_zip.clicked.connect(self._on_generate_zip)

        self._btn_open_folder = QPushButton("📂  Open Folder")
        self._btn_open_folder.setEnabled(False)
        self._btn_open_folder.clicked.connect(self._on_open_folder)

        for btn in (
            self._btn_start,
            self._btn_pause,
            self._btn_resume,
            self._btn_screenshot,
            self._btn_decision,
            self._btn_finish,
            self._btn_generate_zip,
            self._btn_open_folder,
        ):
            tb.addWidget(btn)
            tb.addSeparator()

    # ==================================================================
    # State management helpers
    # ==================================================================

    def _set_idle_state(self) -> None:
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_screenshot.setEnabled(False)
        self._btn_decision.setEnabled(False)
        self._btn_finish.setEnabled(False)
        self._btn_generate_zip.setEnabled(False)
        self._notes_panel.set_recording(False)
        self._browser_status.set_status("Idle", "gray")
        self._browser_status.reset_event_breakdown()

    def _set_recording_state(self) -> None:
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_resume.setEnabled(False)
        self._btn_screenshot.setEnabled(True)
        self._btn_decision.setEnabled(True)
        self._btn_finish.setEnabled(True)
        self._btn_generate_zip.setEnabled(False)
        self._notes_panel.set_recording(True)
        self._browser_status.set_status("Recording", "#198754")

    def _set_paused_state(self) -> None:
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(True)
        self._btn_screenshot.setEnabled(False)
        self._btn_decision.setEnabled(False)
        self._browser_status.set_status("Paused", "#856404")

    def _set_finished_state(self) -> None:
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_screenshot.setEnabled(False)
        self._btn_decision.setEnabled(False)
        self._btn_finish.setEnabled(False)
        self._btn_generate_zip.setEnabled(True)
        self._btn_open_folder.setEnabled(self._session_folder is not None)
        self._notes_panel.set_recording(False)
        self._browser_status.set_status("Finished", "#0d6efd")

    # ==================================================================
    # Toolbar button handlers
    # ==================================================================

    @Slot()
    def _on_start_recording(self) -> None:
        data = self._session_form.get_session_data()
        if not data["agent_name"] or not data["client_reference"]:
            QMessageBox.warning(
                self,
                "Missing Fields",
                "Please fill in at least Agent Name and Client / Reference before starting.",
            )
            return

        # Build session record
        self._session_ts = session_timestamp()
        self._session_record = SessionRecord(**data)
        self._session_record.started_at = now_iso()
        self._session_record.status = "started"

        # Set up file/session stores
        self._session_folder = session_folder_path(
            self._session_ts,
            data["agent_name"],
            data["client_reference"],
        )
        self._file_store = FileStore(self._session_folder)
        self._file_store.initialise()
        self._session_store = SessionStore(self._session_record, self._session_folder)

        # Register atexit to preserve partial data on crash
        atexit.register(self._emergency_flush)

        # Build recorder services
        self._event_recorder = EventRecorder(
            session_id=self._session_record.session_id,
            session_store=self._session_store,
            on_event=self._on_event_recorded_thread,
        )
        self._screenshot_service = ScreenshotService(self._file_store)
        self._snapshot_service = SnapshotService(self._file_store)

        # Launch browser in background thread
        self._browser_controller = BrowserController(
            event_recorder=self._event_recorder,
            screenshot_service=self._screenshot_service,
            parent=self,
        )
        self._browser_controller.page_navigated.connect(self._on_page_navigated)
        self._browser_controller.error_occurred.connect(self._on_browser_error)
        self._browser_controller.browser_closed.connect(self._on_browser_closed)
        self._browser_controller.start()

        # Record system event
        self._event_recorder.record_system(EventType.session_started)

        # Persist initial session data
        self._session_store.write_all()

        # Lock form and update UI
        self._session_form.lock()
        self._timeline.clear_timeline()
        self._event_breakdown = {
            "clicks": 0,
            "inputs": 0,
            "searches": 0,
            "scrolls": 0,
            "virtual_nav": 0,
            "ui_changes": 0,
        }
        self._browser_status.reset_event_breakdown()
        self._browser_status.start_timer()
        self._set_recording_state()
        self.statusBar().showMessage(
            f"Recording started — session folder: {self._session_folder.name}"
        )
        logger.info("Session started: %s", self._session_record.session_id)

    @Slot()
    def _on_pause_recording(self) -> None:
        if self._event_recorder:
            self._event_recorder.is_paused = True
            self._event_recorder.record_system(EventType.recording_paused)
            self._session_store.write_all()
        self._browser_status.stop_timer()
        self._set_paused_state()
        self.statusBar().showMessage("Recording paused — browser events are NOT being captured.")

    @Slot()
    def _on_resume_recording(self) -> None:
        if self._event_recorder:
            self._event_recorder.is_paused = False
            self._event_recorder.record_system(EventType.recording_resumed)
            self._session_store.write_all()
        self._browser_status.start_timer()
        self._set_recording_state()
        self.statusBar().showMessage("Recording resumed.")

    @Slot()
    def _on_manual_screenshot(self) -> None:
        if not self._browser_controller or not self._screenshot_service:
            return
        page = self._browser_controller.get_page()
        if page is None:
            return
        path = self._screenshot_service.take_screenshot(page, "manual_screenshot")
        if path and self._event_recorder:
            url = self._browser_controller.get_current_url()
            title = self._browser_controller.get_current_title()
            self._event_recorder.record_screenshot(url, title, path, manual=True)
            self._session_store.write_all()
            self._browser_status.update_screenshot_count(self._file_store.screenshot_count)
            self.statusBar().showMessage(f"Screenshot saved: {path.name}")

    @Slot()
    def _on_add_decision(self) -> None:
        if not self._session_record:
            return
        url = self._browser_controller.get_current_url() if self._browser_controller else ""
        title = self._browser_controller.get_current_title() if self._browser_controller else ""

        # Optionally take a screenshot for context
        screenshot_ref: Optional[str] = None
        if self._browser_controller and self._screenshot_service:
            page = self._browser_controller.get_page()
            if page:
                path = self._screenshot_service.take_screenshot(page, "decision_context")
                if path:
                    screenshot_ref = str(path.name)
                    self._browser_status.update_screenshot_count(self._file_store.screenshot_count)

        dlg = DecisionDialog(
            session_id=self._session_record.session_id,
            current_url=url,
            current_title=title,
            screenshot_path=screenshot_ref,
            parent=self,
        )
        if dlg.exec() == DecisionDialog.DialogCode.Accepted:
            decision = dlg.get_decision()
            if decision:
                self._session_store.add_decision(decision)
                self._session_store.write_all()
                self.statusBar().showMessage(
                    f"Decision recorded: {decision.decision.value} — {decision.option_name}"
                )

    @Slot()
    def _on_finish_recording(self) -> None:
        if not self._session_record or not self._session_store:
            return
        reply = QMessageBox.question(
            self,
            "Finish Recording",
            "Stop recording and finalise the session?\n\nYou can still generate the ZIP after finishing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._session_record.ended_at = now_iso()
        self._session_record.status = "finished"
        self._event_recorder.record_system(EventType.session_finished)
        self._session_store.write_all()

        self._browser_status.stop_timer()
        self._set_finished_state()

        if self._browser_controller:
            self._browser_controller.stop()

        self._session_form.unlock()
        self.statusBar().showMessage(
            "Session finished — click 'Generate ZIP' to export."
        )
        logger.info("Session finished: %s", self._session_record.session_id)

    @Slot()
    def _on_generate_zip(self) -> None:
        if not self._session_folder or not self._session_record:
            return
        try:
            exporter = ZipExporter()
            self._zip_path = exporter.export(
                session_folder=self._session_folder,
                agent_name=self._session_record.agent_name,
                client_reference=self._session_record.client_reference,
                session_timestamp=self._session_ts or "unknown",
            )
            self._btn_open_folder.setEnabled(True)
            QMessageBox.information(
                self,
                "ZIP Export Successful",
                f"Session exported successfully!\n\nZIP file:\n{self._zip_path}\n\n"
                "Attach this file to your email to the developer.",
            )
            self.statusBar().showMessage(f"ZIP created: {self._zip_path.name}")
        except Exception as exc:
            logger.exception("ZIP export failed")
            QMessageBox.critical(self, "Export Failed", f"Could not generate ZIP:\n{exc}")

    @Slot()
    def _on_open_folder(self) -> None:
        folder = self._zip_path.parent if self._zip_path else self._session_folder
        if folder is None:
            return
        self._open_folder_in_explorer(folder)

    # ==================================================================
    # Browser controller signals (may arrive from non-main thread)
    # ==================================================================

    @Slot(str, str)
    def _on_page_navigated(self, url: str, title: str) -> None:
        self._browser_status.update_url(url)
        self._browser_status.update_title(title)
        if self._session_store:
            self._browser_status.update_event_count(self._session_store.event_count)
        if self._file_store:
            self._browser_status.update_screenshot_count(self._file_store.screenshot_count)

    @Slot(str)
    def _on_browser_error(self, message: str) -> None:
        logger.error("Browser error: %s", message)
        QMessageBox.critical(
            self,
            "Browser Error",
            f"The browser encountered an error:\n\n{message}\n\n"
            "If Playwright is not installed, run:\n  playwright install chromium",
        )
        self._set_idle_state()

    @Slot()
    def _on_browser_closed(self) -> None:
        logger.info("Browser closed")
        if self._session_store and self._session_record:
            if self._session_record.status == "started":
                # Browser closed unexpectedly — preserve partial data
                self._session_record.status = "interrupted"
                self._session_record.ended_at = now_iso()
                self._session_store.write_all()
                self.statusBar().showMessage(
                    "Browser closed — partial session data preserved. You can still generate a ZIP."
                )
                self._set_finished_state()

    # ==================================================================
    # Event bridge: called from BrowserController's thread → Qt queue
    # ==================================================================

    def _on_event_recorded_thread(self, event: BrowserEvent) -> None:
        """Called from the Playwright worker thread — push to queue, never touch Qt objects here."""
        self._event_queue.put_nowait(event)

    @Slot()
    def _drain_event_queue(self) -> None:
        """Called from the Qt main thread timer every 100 ms — drain the event queue."""
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
            except queue.Empty:
                break
            self._timeline.append_event(event)
            if event.url:
                self._browser_status.update_url(event.url)
            if event.page_title:
                self._browser_status.update_title(event.page_title)
            self._update_event_breakdown(event)
            if self._session_store:
                self._browser_status.update_event_count(self._session_store.event_count)
            self._browser_status.update_event_breakdown(
                clicks=self._event_breakdown["clicks"],
                inputs=self._event_breakdown["inputs"],
                searches=self._event_breakdown["searches"],
                scrolls=self._event_breakdown["scrolls"],
                virtual_nav=self._event_breakdown["virtual_nav"],
                ui_changes=self._event_breakdown["ui_changes"],
            )
            if self._file_store:
                self._browser_status.update_screenshot_count(self._file_store.screenshot_count)
            # Persist after every event for crash safety
            if self._session_store:
                self._session_store.write_all()

    def _update_event_breakdown(self, event: BrowserEvent) -> None:
        if event.event_type == EventType.click:
            self._event_breakdown["clicks"] += 1
        elif event.event_type == EventType.input:
            self._event_breakdown["inputs"] += 1
        elif event.event_type == EventType.search_submitted:
            self._event_breakdown["searches"] += 1
        elif event.event_type == EventType.scroll:
            self._event_breakdown["scrolls"] += 1
        elif event.event_type == EventType.ui_changed:
            self._event_breakdown["ui_changes"] += 1
        elif event.event_type == EventType.page_navigated:
            if event.metadata and event.metadata.get("navigation_kind") == "virtual":
                self._event_breakdown["virtual_nav"] += 1

    # ==================================================================
    # Notes panel slot
    # ==================================================================

    @Slot(str, str)
    def _on_note_submitted(self, note_type_value: str, note_text: str) -> None:
        if not self._session_record or not self._session_store:
            return

        try:
            # Use UI-cached browser status text to avoid thread-unsafe
            # Playwright calls from the Qt main thread.
            url = self._browser_status.current_url()
            title = self._browser_status.current_title()

            # Find the NoteType enum member by value
            note_type_enum = NoteType.other
            for nt in NoteType:
                if nt.value == note_type_value:
                    note_type_enum = nt
                    break

            from app.utils.time_utils import now_iso
            note = ReasoningNote(
                session_id=self._session_record.session_id,
                timestamp=now_iso(),
                note_type=note_type_enum,
                note_text=note_text,
                url=url or None,
                page_title=title or None,
                screenshot_path=None,
            )
            self._session_store.add_note(note)
            self._session_store.write_all()

            self.statusBar().showMessage(f"Note added: [{note_type_value}]")
        except Exception:
            logger.exception("Failed to add note")
            self.statusBar().showMessage("Failed to add note. See logs for details.")

    # ==================================================================
    # Crash recovery
    # ==================================================================

    def _emergency_flush(self) -> None:
        """atexit handler — flush any remaining in-memory data to disk."""
        if self._session_store:
            try:
                self._session_store.write_all()
                logger.info("Emergency flush completed")
            except Exception:
                pass

    # ==================================================================
    # Platform file explorer
    # ==================================================================

    @staticmethod
    def _open_folder_in_explorer(folder: Path) -> None:
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(str(folder))
            elif system == "Darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            logger.warning("Could not open folder in file explorer", exc_info=True)

    # ==================================================================
    # Close event
    # ==================================================================

    def closeEvent(self, event) -> None:
        if self._session_record and self._session_record.status in ("started",):
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "A recording session is still active.\n\n"
                "Closing will interrupt the session. Partial data will be saved.\n\n"
                "Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        self._emergency_flush()
        if self._browser_controller:
            self._browser_controller.stop()
            self._browser_controller.wait(3000)
        super().closeEvent(event)
