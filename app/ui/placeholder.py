"""A simple placeholder page used until each real page is built (Phases 2-7)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    """Centered title + note, shown for pages not yet implemented."""

    def __init__(self, title: str, note: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(heading)

        if note:
            sub = QLabel(note)
            sub.setObjectName("pageNote")
            sub.setAlignment(Qt.AlignCenter)
            sub.setWordWrap(True)
            layout.addWidget(sub)
