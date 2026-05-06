"""Decision entry dialog."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.schemas.decision_schema import Decision, DecisionRecord, DecisionType, TierBucket
from app.utils.time_utils import now_iso


class DecisionDialog(QDialog):
    """Modal dialog for recording a structured decision about a quote option."""

    def __init__(
        self,
        session_id: str,
        current_url: str = "",
        current_title: str = "",
        screenshot_path: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_id = session_id
        self._current_url = current_url
        self._current_title = current_title
        self._screenshot_path = screenshot_path
        self.setWindowTitle("Add Decision Record")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._option_name = QLineEdit()
        self._option_name.setPlaceholderText("e.g. Westin Resort Cancun — Junior Suite")

        self._vendor = QLineEdit()
        self._vendor.setPlaceholderText("e.g. Booking.com / Brand website")

        self._option_url = QLineEdit()
        self._option_url.setText(self._current_url)

        self._price_seen = QLineEdit()
        self._price_seen.setPlaceholderText("e.g. 1,250")

        self._currency = QLineEdit()
        self._currency.setPlaceholderText("e.g. USD")
        self._currency.setMaximumWidth(80)

        # Decision type combo
        self._decision_type_combo = QComboBox()
        for dt in DecisionType:
            self._decision_type_combo.addItem(dt.value, dt)

        # Decision outcome
        self._decision_combo = QComboBox()
        for d in Decision:
            self._decision_combo.addItem(d.value, d)

        # Tier bucket
        self._tier_combo = QComboBox()
        for tb in TierBucket:
            self._tier_combo.addItem(tb.value, tb)

        self._reason_text = QPlainTextEdit()
        self._reason_text.setPlaceholderText("Explain why this decision was made…")
        self._reason_text.setMinimumHeight(80)

        self._hard_filter = QCheckBox("Hard filter failed (automatic reject — does not meet criteria)")
        self._reusable_rule = QCheckBox("This decision suggests a reusable protocol rule")

        form.addRow("Option Name *", self._option_name)
        form.addRow("Vendor / Site", self._vendor)
        form.addRow("Option URL", self._option_url)
        form.addRow("Price Seen", self._price_seen)
        form.addRow("Currency", self._currency)
        form.addRow("Decision Type", self._decision_type_combo)
        form.addRow("Decision", self._decision_combo)
        form.addRow("Tier Bucket", self._tier_combo)
        form.addRow("Reason", self._reason_text)
        form.addRow("", self._hard_filter)
        form.addRow("", self._reusable_rule)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_decision(self) -> Optional[DecisionRecord]:
        """Return a validated DecisionRecord, or None if option name is blank."""
        option_name = self._option_name.text().strip()
        if not option_name:
            return None

        return DecisionRecord(
            session_id=self._session_id,
            timestamp=now_iso(),
            decision_type=self._decision_type_combo.currentData(),
            option_name=option_name,
            vendor_or_site=self._vendor.text().strip() or None,
            option_url=self._option_url.text().strip() or None,
            price_seen=self._price_seen.text().strip() or None,
            currency=self._currency.text().strip() or None,
            decision=self._decision_combo.currentData(),
            tier_bucket=self._tier_combo.currentData(),
            reason_text=self._reason_text.toPlainText().strip(),
            hard_filter_failed=self._hard_filter.isChecked(),
            reusable_rule_candidate=self._reusable_rule.isChecked(),
            screenshot_path=self._screenshot_path,
        )
