"""Session setup form widget."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class SessionFormWidget(QWidget):
    """Form for entering quote session metadata before recording starts."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Quote Session Setup")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.agent_name = QLineEdit()
        self.agent_name.setPlaceholderText("e.g. Alice Smith")

        self.client_reference = QLineEdit()
        self.client_reference.setPlaceholderText("e.g. Gomez Family / REF-2026-042")

        self.destination = QLineEdit()
        self.destination.setPlaceholderText("e.g. Belize + Guatemala, 10 days")

        self.travel_dates = QLineEdit()
        self.travel_dates.setPlaceholderText("e.g. 10/08/2026 al 20/08/2026")
        self.travel_dates.setToolTip(
            "Formato requerido: DD/MM/YYYY o DD/MM/YYYY al DD/MM/YYYY"
        )
        date_regex = QRegularExpression(
            r"^\d{2}/\d{2}/\d{4}(\s*(al|a|to|-)\s*\d{2}/\d{2}/\d{4})?$"
        )
        self.travel_dates.setValidator(QRegularExpressionValidator(date_regex, self.travel_dates))

        self.travelers = QLineEdit()
        self.travelers.setPlaceholderText("e.g. 2 adults, 1 child (age 8)")

        self.budget = QLineEdit()
        self.budget.setPlaceholderText("e.g. $6,000 USD total")

        self.trip_type = QLineEdit()
        self.trip_type.setPlaceholderText("e.g. adventure / luxury / family / honeymoon")

        self.special_requirements = QLineEdit()
        self.special_requirements.setPlaceholderText("e.g. vegetarian, wheelchair accessible")

        self.client_request_notes = QPlainTextEdit()
        self.client_request_notes.setPlaceholderText(
            "Free-form notes about what the client asked for…"
        )
        self.client_request_notes.setMaximumHeight(80)

        form.addRow("Agent Name *", self.agent_name)
        form.addRow("Client / Reference *", self.client_reference)
        form.addRow("Destination *", self.destination)
        form.addRow("Travel Dates (DD/MM/YYYY)", self.travel_dates)
        form.addRow("Travelers", self.travelers)
        form.addRow("Budget", self.budget)
        form.addRow("Trip Type", self.trip_type)
        form.addRow("Special Requirements", self.special_requirements)
        form.addRow("Client Request Notes", self.client_request_notes)

        outer.addWidget(box)

    def get_session_data(self) -> dict:
        """Return a dict matching SessionRecord field names."""
        return {
            "agent_name": self.agent_name.text().strip(),
            "client_reference": self.client_reference.text().strip(),
            "destination": self.destination.text().strip(),
            "travel_dates": self.travel_dates.text().strip(),
            "travelers": self.travelers.text().strip(),
            "budget": self.budget.text().strip(),
            "trip_type": self.trip_type.text().strip(),
            "special_requirements": self.special_requirements.text().strip(),
            "client_request_notes": self.client_request_notes.toPlainText().strip(),
        }

    def lock(self) -> None:
        """Disable all fields once recording has started."""
        for widget in (
            self.agent_name,
            self.client_reference,
            self.destination,
            self.travel_dates,
            self.travelers,
            self.budget,
            self.trip_type,
            self.special_requirements,
            self.client_request_notes,
        ):
            widget.setEnabled(False)

    def unlock(self) -> None:
        """Re-enable fields (e.g. after a session is finished)."""
        for widget in (
            self.agent_name,
            self.client_reference,
            self.destination,
            self.travel_dates,
            self.travelers,
            self.budget,
            self.trip_type,
            self.special_requirements,
            self.client_request_notes,
        ):
            widget.setEnabled(True)
