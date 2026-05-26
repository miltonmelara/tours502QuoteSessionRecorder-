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

# Some airline/vendor booking flows use sensitive bot and fraud checks.
# On these domains we avoid injecting DOM listeners and automatic full-page
# screenshots. Navigation is still recorded from Playwright browser events.
BROWSER_PASSIVE_DOMAINS: list[str] = [
    "aireuropa.com",
]

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
# Prefer a real installed browser for airline/vendor sites that treat
# Playwright's bundled "Chrome for Testing" differently from normal Chrome.
# Playwright channel names: chrome, msedge, chromium.
BROWSER_CHANNEL: str = "chrome"
BROWSER_FALLBACK_CHANNELS: list[str] = [
    "msedge",
    "chromium",
]
BROWSER_EXECUTABLE_PATH: str = ""
BROWSER_EXECUTABLE_CANDIDATES: list[str] = [
    "/opt/google/chrome/chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/opt/microsoft/msedge/msedge",
    "/usr/bin/microsoft-edge",
    "/usr/bin/microsoft-edge-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    "/opt/brave.com/brave/brave",
    "/usr/bin/brave-browser",
]
BROWSER_USE_PERSISTENT_PROFILE: bool = True
BROWSER_PROFILE_DIR: Path = BASE_DIR / "browser_profile" / "chrome"
