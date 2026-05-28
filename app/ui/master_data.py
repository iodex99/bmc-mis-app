"""Master Data page — CRUD for every flexible master table.

Entities, cost centres, managers, employees, clients, services and annual
targets can all be added, edited and (soft-)deleted here. Records referenced by
historical data are deactivated rather than destroyed, so past periods stay
intact.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any

from PySide6.QtCore import Qt  # noqa: F401  (used in setElideMode)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import repository as repo
from ..util import fmt_inr


# --- Field & table specifications -------------------------------------------

@dataclass
class Field:
    """One editable column of a master table."""
    key: str
    label: str
    kind: str = "text"          # text | float | choice | fk
    fk_table: str = ""          # for kind == 'fk'
    choices: list[str] = dc_field(default_factory=list)  # for kind == 'choice'
    optional: bool = False      # fk may be left empty


@dataclass
class TableSpec:
    """Describes a master table and how to edit it."""
    table: str
    title: str
    fields: list[Field]
    soft_delete: bool = True    # deactivate vs hard delete
    order_by: str = "id"


SPECS: list[TableSpec] = [
    TableSpec("entities", "Entities", [
        Field("name", "Entity name"),
    ]),
    TableSpec("cost_centres", "Cost Centres", [
        Field("code", "Code"),
        Field("name", "Name"),
        Field("cc_type", "Type", "choice", choices=["partner", "office"]),
    ]),
    TableSpec("managers", "Managers", [
        Field("code", "Code"),
        Field("name", "Name"),
        Field("cost_centre_id", "Cost centre", "fk", fk_table="cost_centres",
              optional=True),
    ]),
    TableSpec("employees", "Employees", [
        Field("emp_code", "Emp code", optional=True),
        Field("name", "Name"),
        Field("category", "Category", "choice",
              choices=["Employee", "CA Article", "CMA Article"]),
        Field("manager_id", "Manager", "fk", fk_table="managers", optional=True),
        Field("default_cost_centre_id", "Default cost centre", "fk",
              fk_table="cost_centres", optional=True),
    ]),
    TableSpec("clients", "Clients", [
        Field("canonical_name", "Client name"),
        Field("cost_centre_id", "Cost centre", "fk", fk_table="cost_centres",
              optional=True),
    ], order_by="canonical_name"),
    TableSpec("services", "Services", [
        Field("name", "Service name"),
    ], order_by="name"),
    TableSpec("targets", "Annual Targets", [
        Field("financial_year", "Financial year (e.g. 2025-26)"),
        Field("cost_centre_id", "Cost centre", "fk", fk_table="cost_centres"),
        Field("target_amount", "Target amount", "float"),
    ], soft_delete=False),
]


# --- Record add/edit dialog --------------------------------------------------

class RecordDialog(QDialog):
    """Form dialog to add or edit one record, driven by a TableSpec."""

    def __init__(self, spec: TableSpec, record: dict[str, Any] | None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.record = record or {}
        self.setWindowTitle(
            f"{'Edit' if record else 'Add'} — {spec.title.rstrip('s')}")
        self.setMinimumWidth(380)

        form = QFormLayout()
        self._widgets: dict[str, QWidget] = {}
        for f in spec.fields:
            w = self._make_widget(f)
            self._widgets[f.key] = w
            form.addRow(f.label + ":", w)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _make_widget(self, f: Field) -> QWidget:
        current = self.record.get(f.key)
        if f.kind == "float":
            w = QDoubleSpinBox()
            w.setRange(0, 1_000_000_000)
            w.setGroupSeparatorShown(True)
            w.setDecimals(2)
            if current is not None:
                w.setValue(float(current))
            return w
        if f.kind == "choice":
            w = QComboBox()
            w.addItems(f.choices)
            if current in f.choices:
                w.setCurrentText(current)
            return w
        if f.kind == "fk":
            w = QComboBox()
            if f.optional:
                w.addItem("(none)", None)
            for fid, label in repo.fk_options(f.fk_table):
                w.addItem(label, fid)
            if current is not None:
                idx = w.findData(current)
                if idx >= 0:
                    w.setCurrentIndex(idx)
            return w
        w = QLineEdit()
        if current is not None:
            w.setText(str(current))
        return w

    def values(self) -> dict[str, Any]:
        """Collect the edited values keyed by column name."""
        out: dict[str, Any] = {}
        for f in self.spec.fields:
            w = self._widgets[f.key]
            if isinstance(w, QDoubleSpinBox):
                out[f.key] = w.value()
            elif isinstance(w, QComboBox):
                out[f.key] = w.currentData() if f.kind == "fk" else w.currentText()
            else:
                out[f.key] = w.text().strip()
        return out

    def _on_accept(self) -> None:
        values = self.values()
        for f in self.spec.fields:
            if f.kind in ("text", "choice") and not f.optional and not values[f.key]:
                QMessageBox.warning(self, "Missing value",
                                    f"'{f.label}' is required.")
                return
        self.accept()


# --- One tab per master table ------------------------------------------------

class RecordTab(QWidget):
    """A table view of one master table with Add / Edit / Delete actions."""

    def __init__(self, spec: TableSpec) -> None:
        super().__init__()
        self.spec = spec
        self._rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_btn = QPushButton("＋ Add new")
        self.add_btn.setObjectName("primary")
        self.edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton(
            "Deactivate" if spec.soft_delete else "Delete")
        self.del_btn.setObjectName("danger")
        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.del_btn.clicked.connect(self._delete)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.del_btn)
        toolbar.addStretch(1)
        if spec.soft_delete:
            self.show_inactive = QCheckBox("Show inactive")
            self.show_inactive.stateChanged.connect(self.reload)
            toolbar.addWidget(self.show_inactive)
        else:
            self.show_inactive = None
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)

        self._fk_maps = {f.fk_table: repo.fk_label_map(f.fk_table)
                         for f in spec.fields if f.kind == "fk"}
        self.reload()

    # -- data ----------------------------------------------------------------
    def reload(self) -> None:
        include_inactive = bool(self.show_inactive and self.show_inactive.isChecked())
        self._fk_maps = {t: repo.fk_label_map(t) for t in self._fk_maps}
        self._rows = repo.fetch_all(
            self.spec.table, include_inactive=include_inactive,
            order_by=self.spec.order_by)
        self._render()

    def _render(self) -> None:
        headers = [f.label for f in self.spec.fields]
        if self.spec.soft_delete:
            headers.append("Status")
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._rows))

        for r, row in enumerate(self._rows):
            for c, f in enumerate(self.spec.fields):
                self.table.setItem(r, c, QTableWidgetItem(self._display(f, row)))
            if self.spec.soft_delete:
                status = "Active" if row.get("active", 1) else "Inactive"
                self.table.setItem(r, len(self.spec.fields),
                                   QTableWidgetItem(status))
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)

    def _display(self, f: Field, row: dict[str, Any]) -> str:
        value = row.get(f.key)
        if value in (None, ""):
            return ""
        if f.kind == "fk":
            return self._fk_maps.get(f.fk_table, {}).get(value, f"#{value}")
        if f.kind == "float":
            return fmt_inr(value, 2)
        return str(value)

    def _selected(self) -> dict[str, Any] | None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        return self._rows[rows.pop()] if rows else None

    # -- actions -------------------------------------------------------------
    def _add(self) -> None:
        dlg = RecordDialog(self.spec, None, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                repo.insert(self.spec.table, dlg.values())
            except Exception as exc:  # e.g. UNIQUE violation
                QMessageBox.critical(self, "Could not add", str(exc))
            self.reload()

    def _edit(self) -> None:
        record = self._selected()
        if not record:
            return
        dlg = RecordDialog(self.spec, record, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                repo.update(self.spec.table, record["id"], dlg.values())
            except Exception as exc:
                QMessageBox.critical(self, "Could not save", str(exc))
            self.reload()

    def _delete(self) -> None:
        record = self._selected()
        if not record:
            return
        if self.spec.soft_delete:
            active = bool(record.get("active", 1))
            verb = "deactivate" if active else "reactivate"
            if QMessageBox.question(
                    self, "Confirm", f"{verb.capitalize()} this record?") \
                    == QMessageBox.Yes:
                repo.set_active(self.spec.table, record["id"], not active)
        else:
            if QMessageBox.question(
                    self, "Confirm", "Delete this record permanently?") \
                    == QMessageBox.Yes:
                try:
                    repo.delete(self.spec.table, record["id"])
                except Exception as exc:
                    QMessageBox.critical(self, "Could not delete", str(exc))
        self.reload()


# --- The page itself ---------------------------------------------------------

class MasterDataPage(QWidget):
    """Tabbed page hosting every master-data table."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("Master Data")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        note = QLabel("Add, edit or deactivate entities, cost centres, "
                      "managers, employees, clients, services and annual "
                      "targets.")
        note.setObjectName("pageNote")
        layout.addWidget(note)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self._tabs: list[RecordTab] = []
        for spec in SPECS:
            tab = RecordTab(spec)
            self._tabs.append(tab)
            self.tabs.addTab(tab, spec.title)
        self.tabs.currentChanged.connect(self._refresh_current)
        layout.addWidget(self.tabs, 1)

    def _refresh_current(self, index: int) -> None:
        # FK dropdowns may have changed on another tab — reload on switch.
        if 0 <= index < len(self._tabs):
            self._tabs[index].reload()
