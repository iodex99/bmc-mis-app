"""Dialog for mapping spreadsheet columns to canonical fields."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# By default a QComboBox / QSpinBox eats wheel events to step through its
# values — which is awful when it sits inside a scroll area. These subclasses
# pass the wheel event up to the parent so the scroll area scrolls instead.

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):  # noqa: N802
        event.ignore()


class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):  # noqa: N802
        event.ignore()
from rapidfuzz import fuzz

from .. import config
from ..importing.fields import fields_for

PREVIEW_ROWS = 18

ROLE_IGNORE = "ignore"
ROLE_SERVICE = "service"
ROLE_TAX = "tax"
_ROLE_LABELS = {
    ROLE_IGNORE: "Ignore",
    ROLE_SERVICE: "Service column (revenue)",
    ROLE_TAX: "Tax / TDS / round-off",
}
_TAX_KEYWORDS = ("gst", "tds", "round", "tax")


class ColumnMappingDialog(QDialog):
    """Shows a file preview and lets the operator map each canonical field.

    For the Sales file type, an extra section lets the operator tag each
    spreadsheet column as **Service** (with a service name) or **Tax** —
    every other column is ignored. This is what makes service-wise MIS
    possible without forcing the user to pre-create voucher splits.
    """

    def __init__(self, grid: list[list], file_type: str,
                 existing: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.grid = grid
        self.file_type = file_type
        self.fields = fields_for(file_type)
        self.setWindowTitle("Map Columns to Fields")
        # Open at a size that fits the current screen, leaving room for the
        # taskbar — so the OK / Cancel buttons are always on-screen.
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        max_h = (avail.height() - 80) if avail else 720
        self.resize(min(980, (avail.width() - 80) if avail else 980),
                    min(720, max_h))
        self.setMinimumSize(720, 480)

        # The dialog itself stays a fixed shell: title at top, OK/Cancel at the
        # bottom, and a scroll area in the middle for everything else — so
        # the buttons never get pushed off-screen no matter how many service
        # columns a file has.
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(QLabel(
            "Set the header row, then map each field to its column. This "
            "layout is remembered — you only do it once per file format."))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_body = QWidget()
        body = QVBoxLayout(scroll_body)
        body.setContentsMargins(0, 0, 4, 0)
        body.setSpacing(10)
        scroll.setWidget(scroll_body)
        root.addWidget(scroll, 1)

        # --- preview table --------------------------------------------------
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setMinimumHeight(180)
        body.addWidget(self.preview)

        # --- header row selector -------------------------------------------
        hdr_row = QHBoxLayout()
        hdr_row.addWidget(QLabel("Header row:"))
        self.header_spin = NoScrollSpinBox()
        self.header_spin.setRange(1, min(len(grid), 60) or 1)
        self.header_spin.valueChanged.connect(self._refresh_labels)
        hdr_row.addWidget(self.header_spin)
        hdr_row.addStretch(1)
        body.addLayout(hdr_row)

        # --- field -> column combos ----------------------------------------
        box = QGroupBox("Field mapping")
        form = QFormLayout(box)
        self.combos: dict[str, QComboBox] = {}
        for f in self.fields:
            combo = NoScrollComboBox()
            self.combos[f.key] = combo
            label = f.label + (" *" if f.required else "")
            form.addRow(label, combo)
        body.addWidget(box)

        # --- per-column roles (sales only) ---------------------------------
        self.roles_box: QGroupBox | None = None
        self.role_table: QTableWidget | None = None
        if file_type == config.FILE_TYPE_SALES:
            self.roles_box = QGroupBox(
                "Service & Tax columns "
                "(revenue is split across multiple service columns)")
            rb = QVBoxLayout(self.roles_box)
            rb.addWidget(QLabel(
                "For each spreadsheet column, pick a role. Service columns "
                "become revenue splits; tax/TDS/round-off columns are summed "
                "into the tax total and excluded from revenue."))
            self.role_table = QTableWidget(0, 3)
            self.role_table.setHorizontalHeaderLabels(
                ["Column", "Role", "Service name"])
            self.role_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeToContents)
            self.role_table.horizontalHeader().setStretchLastSection(True)
            self.role_table.setEditTriggers(
                QAbstractItemView.NoEditTriggers)
            self.role_table.setMinimumHeight(200)
            rb.addWidget(self.role_table)
            body.addWidget(self.roles_box)

        body.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        existing = existing or {}
        self._n_cols = max((len(r) for r in grid), default=0)
        self.header_spin.setValue(
            (existing.get("header_row", _guess_header(grid))) + 1)
        self._render_preview()
        self._refresh_labels()
        self._apply_existing_fields(existing.get("columns", {}))
        if self.role_table is not None:
            self._build_roles_table(existing.get("service_map", {}),
                                    existing.get("tax_cols", []))

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
            target = keep if keep is not None and keep >= 0 else \
                _suggest(f.label, header)
            idx = combo.findData(target if target is not None else -1)
            combo.setCurrentIndex(max(idx, 0))
            combo.blockSignals(False)
        for r in range(self.preview.rowCount()):
            for c in range(self.preview.columnCount()):
                item = self.preview.item(r, c)
                if item:
                    item.setBackground(
                        Qt.yellow if r == self.header_index() else Qt.white)
        if self.role_table is not None:
            self._build_roles_table(self._collect_service_map(),
                                    self._collect_tax_cols())

    def _apply_existing_fields(self, columns: dict[str, int]) -> None:
        for key, idx in columns.items():
            combo = self.combos.get(key)
            if combo:
                pos = combo.findData(idx)
                if pos >= 0:
                    combo.setCurrentIndex(pos)

    # -- roles table (sales only) -------------------------------------------
    def _build_roles_table(self, service_map: dict, tax_cols: list) -> None:
        assert self.role_table is not None
        header = self.grid[self.header_index()] if self.grid else []
        # Columns already claimed by the field mapping shouldn't appear here.
        claimed = {combo.currentData() for combo in self.combos.values()
                   if combo.currentData() is not None and combo.currentData() >= 0}
        # Normalise existing mapping keys to int.
        sm = {int(k): v for k, v in (service_map or {}).items()}
        tc = set(int(c) for c in (tax_cols or []))

        self.role_table.setRowCount(0)
        for col_idx in range(self._n_cols):
            if col_idx in claimed:
                continue
            head_text = (str(header[col_idx]).strip()
                         if col_idx < len(header) and header[col_idx] else "")
            r = self.role_table.rowCount()
            self.role_table.insertRow(r)
            self.role_table.setItem(
                r, 0, QTableWidgetItem(f"Col {col_idx + 1}  "
                                       f"{head_text}".strip()))
            self.role_table.item(r, 0).setData(Qt.UserRole, col_idx)

            role_combo = NoScrollComboBox()
            for key, lab in _ROLE_LABELS.items():
                role_combo.addItem(lab, key)
            default_role = (ROLE_SERVICE if col_idx in sm else
                            ROLE_TAX if col_idx in tc else
                            _suggest_role(head_text))
            role_combo.setCurrentIndex(
                role_combo.findData(default_role))
            role_combo.currentIndexChanged.connect(
                lambda _i, rr=r: self._on_role_changed(rr))
            self.role_table.setCellWidget(r, 1, role_combo)

            name_edit = QLineEdit(sm.get(col_idx, head_text))
            name_edit.setEnabled(default_role == ROLE_SERVICE)
            self.role_table.setCellWidget(r, 2, name_edit)

    def _on_role_changed(self, row: int) -> None:
        role = self.role_table.cellWidget(row, 1).currentData()
        name_edit = self.role_table.cellWidget(row, 2)
        name_edit.setEnabled(role == ROLE_SERVICE)
        if role == ROLE_SERVICE and not name_edit.text().strip():
            # default to the column header text
            col_idx = self.role_table.item(row, 0).data(Qt.UserRole)
            header = self.grid[self.header_index()]
            if col_idx < len(header) and header[col_idx]:
                name_edit.setText(str(header[col_idx]).strip())

    def _collect_service_map(self) -> dict[int, str]:
        out: dict[int, str] = {}
        if self.role_table is None:
            return out
        for r in range(self.role_table.rowCount()):
            role = self.role_table.cellWidget(r, 1).currentData()
            if role == ROLE_SERVICE:
                col_idx = self.role_table.item(r, 0).data(Qt.UserRole)
                name = self.role_table.cellWidget(r, 2).text().strip()
                if name:
                    out[col_idx] = name
        return out

    def _collect_tax_cols(self) -> list[int]:
        out: list[int] = []
        if self.role_table is None:
            return out
        for r in range(self.role_table.rowCount()):
            role = self.role_table.cellWidget(r, 1).currentData()
            if role == ROLE_TAX:
                out.append(self.role_table.item(r, 0).data(Qt.UserRole))
        return out

    # -- save -----------------------------------------------------------------
    def _on_accept(self) -> None:
        mapping = self.column_map()
        missing = [f.label for f in self.fields
                   if f.required and f.key not in mapping]
        if missing:
            QMessageBox.warning(self, "Incomplete mapping",
                                "These required fields are not mapped:\n  • "
                                + "\n  • ".join(missing))
            return
        if self.file_type == config.FILE_TYPE_SALES \
                and not self._collect_service_map():
            QMessageBox.warning(
                self, "No service columns",
                "Mark at least one column as a 'Service column' so the "
                "importer knows where revenue is.")
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

    def service_map(self) -> dict[int, str]:
        return self._collect_service_map() if self.role_table else {}

    def tax_cols(self) -> list[int]:
        return self._collect_tax_cols() if self.role_table else []

    def data_start(self) -> int:
        return self.header_index() + 1


# --- helpers ----------------------------------------------------------------

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


def _suggest_role(header_text: str) -> str:
    """Auto-guess a column's role from its header text."""
    if not header_text:
        return ROLE_IGNORE
    low = header_text.lower()
    if any(k in low for k in _TAX_KEYWORDS):
        return ROLE_TAX
    return ROLE_IGNORE
