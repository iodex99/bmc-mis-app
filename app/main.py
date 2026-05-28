"""Entry point for the Bilimoria Mehta & Co. MIS Generator desktop app.

Run with:  python -m app.main
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from . import config
from .database import init_db
from .ui.main_window import MainWindow
from .ui.style import STYLESHEET


def _force_light_palette(app: QApplication) -> None:
    """Apply a light palette so Windows dark-mode does not bleed through."""
    p = QPalette()
    white = QColor("#FFFFFF")
    slate = QColor("#F1F5F9")
    navy = QColor("#0F172A")
    border = QColor("#CBD5E1")
    indigo = QColor("#4F46E5")
    p.setColor(QPalette.Window, slate)
    p.setColor(QPalette.WindowText, navy)
    p.setColor(QPalette.Base, white)
    p.setColor(QPalette.AlternateBase, slate)
    p.setColor(QPalette.Text, navy)
    p.setColor(QPalette.Button, white)
    p.setColor(QPalette.ButtonText, navy)
    p.setColor(QPalette.ToolTipBase, navy)
    p.setColor(QPalette.ToolTipText, white)
    p.setColor(QPalette.Highlight, indigo)
    p.setColor(QPalette.HighlightedText, white)
    p.setColor(QPalette.PlaceholderText, QColor("#94A3B8"))
    p.setColor(QPalette.Mid, border)
    p.setColor(QPalette.Light, white)
    p.setColor(QPalette.Dark, navy)
    app.setPalette(p)


def main() -> int:
    config.ensure_dirs()
    init_db()  # idempotent: creates schema + seeds on first run

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.ORG_NAME)
    app.setStyle("Fusion")             # consistent cross-platform rendering
    _force_light_palette(app)          # ignore Windows dark mode
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
