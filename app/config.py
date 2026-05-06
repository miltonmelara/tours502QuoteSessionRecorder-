"""
Central configuration for Tours502 Quote Session Recorder.

Keep all tunable constants here so they never scatter across modules.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
APP_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
EXPORTS_DIR: Path = BASE_DIR / "exports"
LOGS_DIR: Path = BASE_DIR / "logs"

# Ensure base folders exist at import time
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Screenshot behaviour
# ---------------------------------------------------------------------------
# Take a screenshot automatically after every page navigation
SCREENSHOT_ON_NAVIGATION: bool = True
# Take a screenshot when a note is added
SCREENSHOT_ON_NOTE: bool = True
# Take a screenshot after every click (can make ZIPs large — off by default)
SCREENSHOT_ON_CLICK: bool = False

# ---------------------------------------------------------------------------
# Redaction — field names/ids/placeholders/types that must never be stored
# ---------------------------------------------------------------------------
REDACTED_FIELD_KEYWORDS: list[str] = [
    "password",
    "passwd",
    "pass",
    "pwd",
    "secret",
    "token",
    "auth",
    "credit",
    "card",
    "cvv",
    "cvc",
    "ccv",
    "expiry",
    "expiration",
    "cardnumber",
    "card_number",
    "pan",
    "payment",
    "billing",
    "account",
    "routing",
    "iban",
    "swift",
    "bic",
    "ssn",
    "sin",
    "dpi",
    "passport",
    "nationalid",
    "national_id",
    "idnumber",
    "id_number",
    "taxid",
    "tax_id",
    "dob",
    "birthdate",
    "date_of_birth",
]

REDACTED_INPUT_TYPES: list[str] = [
    "password",
    "hidden",
]

REDACTED_PLACEHOLDER = "[REDACTED]"

# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
BROWSER_HEADLESS: bool = False
BROWSER_CHANNEL: str = "chromium"  # always use chromium for consistency
