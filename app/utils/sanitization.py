"""Sensitive-value redaction for browser input capture."""

from __future__ import annotations

from app.config import REDACTED_FIELD_KEYWORDS, REDACTED_INPUT_TYPES, REDACTED_PLACEHOLDER


def _matches_sensitive_keyword(text: str) -> bool:
    """Return True if *text* contains any redaction keyword (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in REDACTED_FIELD_KEYWORDS)


def redact_sensitive_value(
    value: str,
    *,
    input_type: str = "",
    field_name: str = "",
    field_id: str = "",
    field_placeholder: str = "",
) -> tuple[str, bool]:
    """Decide whether *value* should be redacted.

    Returns a tuple of (stored_value, was_redacted).

    Redaction triggers:
    - input type is in REDACTED_INPUT_TYPES (e.g. "password", "hidden")
    - any of field_name, field_id, or field_placeholder contains a sensitive keyword
    """
    if input_type.lower() in REDACTED_INPUT_TYPES:
        return REDACTED_PLACEHOLDER, True

    for hint in (field_name, field_id, field_placeholder):
        if hint and _matches_sensitive_keyword(hint):
            return REDACTED_PLACEHOLDER, True

    return value, False
