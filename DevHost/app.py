"""
app.py — application bootstrap.

This is the PyInstaller entry point:
    pyinstaller --onefile --windowed --uac-admin app.py

The --uac-admin manifest flag on the EXE handles UAC at the OS level.
The Python-side check in admin_service handles the "run from source" case.
"""

import sys
import logging
from pathlib import Path

# ── Logging setup (must happen before any service imports) ──────────────────
_BASE_DIR = Path(__file__).resolve().parent
_LOG_DIR = _BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(_LOG_DIR / "devhost.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# ── Admin elevation (Python-side, for running from source) ──────────────────
from services.admin_service import ensure_admin  # noqa: E402
ensure_admin()

# ── Qt application ──────────────────────────────────────────────────────────
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import Qt               # noqa: E402
from PySide6.QtGui import QFontDatabase     # noqa: E402

from services.settings_service import SettingsService  # noqa: E402
from ui.main_window import MainWindow                  # noqa: E402
from ui.styles import MAIN_STYLESHEET                  # noqa: E402


def main() -> int:
    logger.info("DevHost starting up.")

    app = QApplication(sys.argv)
    app.setApplicationName("DevHost")
    app.setApplicationDisplayName("DevHost — Local Domain Manager")
    app.setOrganizationName("DevHost")
    app.setApplicationVersion("1.0.0")

    # High-DPI support
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Apply global stylesheet
    app.setStyleSheet(MAIN_STYLESHEET)

    settings = SettingsService()
    window = MainWindow(settings)
    window.show()

    logger.info("Event loop started.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
