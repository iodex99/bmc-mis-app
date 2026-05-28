"""Dialog for mapping spreadsheet columns to canonical fields (Phase 3)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from rapidfuzz import fuzz

from ..importing.fields import fields_for

PREVIEW_ROWS = 18


class ColumnMappingDialog(QDialog):
    """Shows a file preview and lets the operator map each canonical field."""

    def __init__(self, grid: list[list], file_type: str,
                 existing: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.grid = grid
        self.fields = fields_for(file_type)
        self.setWindowTitle("Map Columns to Fields")
        self.resize(900, 620)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Set the header row, then map each field to its column. This layout "
            "is remembered — you only do it once per file format."))

        # --- preview table --------------------------------------------------
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.preview, 1)

        # --- header row selector -------------------------------------------
        hdr_row = QHBoxLayout()
        hdr_row.addWidget(QLabel("Header row:"))
        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, min(len(grid), 60) or 1)
        self.header_spin.valueChanged.connect(self._refresh_labels)
        hdr_row.addWidget(self.header_spin)
        hdr_row.addStretch(1)
        root.addLayout(hdr_row)

        # --- field -> column combos ----------------------------------------
        box = QGroupBox("Field mapping")
        form = QFormLayout(box)
        self.combos: dict[str, QComboBox] = {}
        for f in self.fields:
            combo = QComboBox()
            self.combos[f.key] = combo
            label = f.label + (" *" if f.required else "")
            form.addRow(label, combo)
        root.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        existing = existing or {}
        self._n_cols = max((len(r) for r in grid), default=0)
        self.header_spin.setValue((existing.get("header_row", _guess_header(grid))) + 1)
        self._render_preview()
        self._refresh_labels()
        self._apply_existing(existing.get("columns", {}))

    # -- internals -----------------------------------------------------------
    def header_index(self) -> int:
        return self.header_spin.value() - 1

    def _render_preview(self) -> None:
        rows = self.grid[:PREVIEW_ROWS]
        self.preview.setRowCount(len(rows))
        self.preview.setColumnCount(self._n_cols)
        self.preview.setHorizontalHeaderLabels(
            [f"Col {i + 1}" for i in range(self._n_cols)])
        for r, row in enumerate(rows):
            self.preview.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
            for c in range(self._n_cols):
                val = row[c] if c < len(row) else None
                self.preview.setItem(
                    r, c, QTableWidgetItem("" if val is None else str(val)))
        self.preview.resizeColumnsToContents()

    def _column_labels(self) -> list[str]:
        header = self.grid[self.header_index()] if self.grid else []
        labels = []
        for i in range(self._n_cols):
            txt = str(header[i]).strip() if i < len(header) and header[i] else ""
            labels.append(f"Col {i + 1}" + (f"  ({txt})" if txt else ""))
        return labels

    def _refresh_labels(self) -> None:
        labels = self._column_labels()
        header = self.grid[self.header_index()] if self.grid else []
        for f in self.fields:
            combo = self.combos[f.key]
            keep = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— not mapped —", -1)
            for i, lab in enumerate(labels):
                combo.addItem(lab, i)
            # restore or auto-suggest
            target = keep if keep is not None and keep >= 0 else \
                _suggest(f.label, header)
            idx = combo.findData(target if target is not None else -1)
            combo.setCurrentIndex(max(idx, 0))
            combo.blockSignals(False)
        # highlight header row
        for r in range(self.preview.rowCount()):
            for c in range(self.preview.columnCount()):
                item = self.preview.item(r, c)
                if item:
                    item.setBackground(
                        Qt.yellow if r == self.header_index() else Qt.white)

    def _apply_existing(self, columns: dict[str, int]) -> None:
        for key, idx in columns.items():
            combo = self.combos.get(key)
            if combo:
                pos = combo.findData(idx)
                if pos >= 0:
                    combo.setCurrentIndex(pos)

    def _on_accept(self) -> None:
        mapping = self.column_map()
        missing = [f.label for f in self.fields
                   if f.required and f.key not in mapping]
        if missing:
            QMessageBox.warning(self, "Incomplete mapping",
                                "These required fields are not mapped:\n  • "
                                + "\n  • ".join(missing))
            return
        self.accept()

    # -- results -------------------------------------------------------------
    def column_map(self) -> dict[str, int]:
        out = {}
        for key, combo in self.combos.items():
            idx = combo.currentData()
            if idx is not None and idx >= 0:
                out[key] = idx
        return out

    def data_start(self) -> int:
        return self.header_index() + 1


def _guess_header(grid: list[list]) -> int:
    best, score = 0, -1
    for i, row in enumerate(grid[:40]):
        s = sum(1 for c in row if isinstance(c, str) and c.strip())
        if s > score:
            best, score = i, s
    return best


def _suggest(field_label: str, header: list) -> int | None:
    """Fuzzy-match a canonical field label to a header cell."""
    best, best_score = None, 55
    for i, cell in enumerate(header):
        if not cell:
            continue
        score = fuzz.partial_ratio(field_label.lower(), str(cell).lower())
        if score > best_score:
            best, best_score = i, score
    return best
