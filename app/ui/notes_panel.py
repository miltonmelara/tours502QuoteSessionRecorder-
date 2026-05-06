"""Reasoning notes panel widget."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.schemas.note_schema import NoteType


class NotesPanelWidget(QWidget):
    """Panel for adding human reasoning notes during a recording session."""

    # Emitted when a note is submitted: (note_type_value: str, note_text: str)
    note_submitted = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ---- Input area ----
        input_box = QGroupBox("Add Reasoning Note")
        input_layout = QFormLayout(input_box)

        self._type_combo = QComboBox()
        for nt in NoteType:
            self._type_combo.addItem(nt.value, nt)

        self._note_text = QPlainTextEdit()
        self._note_text.setPlaceholderText(
            "Describe your reasoning here (why you chose this site, "
            "why you rejected an option, what rule applies, etc.)…"
        )
        self._note_text.setMinimumHeight(80)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Note")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._submit_note)
        btn_row.addStretch()
        btn_row.addWidget(self._add_btn)

        input_layout.addRow("Note Type:", self._type_combo)
        input_layout.addRow("Note:", self._note_text)
        input_layout.addRow("", btn_row)

        # ---- History list ----
        history_box = QGroupBox("Notes This Session")
        history_layout = QVBoxLayout(history_box)
        self._history_list = QListWidget()
        self._history_list.setWordWrap(True)
        self._history_list.setMaximumHeight(160)
        history_layout.addWidget(self._history_list)

        outer.addWidget(input_box)
        outer.addWidget(history_box)

    def set_recording(self, active: bool) -> None:
        """Enable/disable the Add Note button based on recording state."""
        self._add_btn.setEnabled(active)

    def _submit_note(self) -> None:
        text = self._note_text.toPlainText().strip()
        if not text:
            return
        note_type: NoteType = self._type_combo.currentData()
        self.note_submitted.emit(note_type.value, text)

        # Add to history list
        item = QListWidgetItem(f"[{note_type.value}]  {text[:80]}{'…' if len(text) > 80 else ''}")
        self._history_list.addItem(item)
        self._history_list.scrollToBottom()

        # Clear input
        self._note_text.clear()
