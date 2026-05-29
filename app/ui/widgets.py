"""Small shared widget subclasses and table helpers."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


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


# --- table helpers ----------------------------------------------------------

def setup_data_table(table: QTableWidget, *, multi_select: bool = False) -> None:
    """Apply the standard read-only / row-select look to a data table."""
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(
        QTableWidget.ExtendedSelection if multi_select
        else QTableWidget.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.horizontalHeader().setHighlightSections(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


def fill_table_with_actions(
    table: QTableWidget,
    headers: list[str],
    rows: list[list],
    *,
    action_label: str | list[str] = "Resolve →",
    action_callback: Callable[[int], None] | None = None,
    secondary_label: str | None = None,
    secondary_callback: Callable[[int], None] | None = None,
    secondary_object_name: str = "rowAction",
    status_for_row: Callable[[int], tuple[str, str]] | None = None,
    stretch_col: int | None = None,
) -> None:
    """Fill a table with an inline action button (and optional status) per row.

    *status_for_row(row_index) -> (text, object_name)* renders a small pill in a
    Status column on the left. *secondary_label / secondary_callback* adds a
    second button (e.g. Deactivate / Delete) alongside the primary one.
    """
    has_status = status_for_row is not None
    has_action = action_callback is not None
    extra = (1 if has_status else 0) + (1 if has_action else 0)
    all_headers = (
        (["Status"] if has_status else [])
        + headers
        + (["Actions"] if has_action else [])
    )
    table.setColumnCount(len(all_headers))
    table.setHorizontalHeaderLabels(all_headers)
    table.setRowCount(len(rows))

    offset = 1 if has_status else 0
    for r, row in enumerate(rows):
        if has_status:
            text, kind = status_for_row(r)
            pill = QLabel(f"  {text}  ")
            pill.setAlignment(Qt.AlignCenter)
            pill.setObjectName(kind)        # "statusOk" / "statusWarn" / "statusBad"
            table.setCellWidget(r, 0, pill)
        for c, val in enumerate(row):
            item = QTableWidgetItem("" if val is None else str(val))
            table.setItem(r, c + offset, item)
        if has_action:
            label = (action_label if isinstance(action_label, str)
                     else action_label[r])
            actions_cell = QWidget()
            cell_lay = QHBoxLayout(actions_cell)
            cell_lay.setContentsMargins(4, 2, 4, 2)
            cell_lay.setSpacing(6)
            cell_lay.addStretch(1)
            btn = QPushButton(label)
            btn.setObjectName("rowAction")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, row_idx=r:
                action_callback(row_idx))      # type: ignore[misc]
            cell_lay.addWidget(btn)
            if secondary_label and secondary_callback:
                btn2 = QPushButton(secondary_label)
                btn2.setObjectName(secondary_object_name)
                btn2.setCursor(Qt.PointingHandCursor)
                btn2.clicked.connect(
                    lambda _checked=False, row_idx=r:
                    secondary_callback(row_idx))  # type: ignore[misc]
                cell_lay.addWidget(btn2)
            table.setCellWidget(r, len(all_headers) - 1, actions_cell)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    target = (stretch_col + offset) if stretch_col is not None else (offset)
    target = min(target, len(all_headers) - 1)
    header.setSectionResizeMode(target, QHeaderView.Stretch)
    table.setRowHeight(0, 36) if rows else None
    for r in range(len(rows)):
        table.setRowHeight(r, 40)
