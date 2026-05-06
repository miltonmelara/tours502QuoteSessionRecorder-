"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.config import APP_VERSION
from app.utils.logging_setup import configure_logging


def main() -> None:
    configure_logging()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Tours502 Quote Session Recorder v%s starting", APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName("Tours502 Quote Session Recorder")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Tours502")

    # Import here to ensure logging is configured before any module-level code runs
    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
