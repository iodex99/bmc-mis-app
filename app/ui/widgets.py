"""Small shared widget subclasses."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QSpinBox


# QComboBox / QSpinBox eat the mouse wheel by default — which is awful when
# they sit inside a scroll area: the user tries to scroll, the dropdown's
# value flips instead. These subclasses ignore the wheel event so it bubbles
# up to the surrounding scroll area.

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):  # noqa: N802 (Qt name)
        event.ignore()


class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):  # noqa: N802
        event.ignore()
