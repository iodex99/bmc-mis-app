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
    QFileDialog,
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

import datetime as _dt

from .. import repository as repo
from ..importing import excel_reader
from ..services import resolution
from ..services.calc import financial_year, normalize_fy


def _fy_choices() -> list[str]:
    """Financial years to offer in the Annual Targets dropdown.

    A window around the current FY (3 back → 30 forward) merged with any
    FY already stored on a target row, newest first. Lets the operator
    pick instead of re-typing '2026-27' (and mistyping it as '2026 - 27',
    the bug behind targets silently reading 0 pre-v0.3.73). It's still an
    editable combo, so a year beyond the window can be typed if ever
    needed."""
    today = _dt.date.today()
    cur = financial_year(f"{today.year:04d}-{today.month:02d}")
    start = int(cur.split("-")[0])
    years = {f"{y}-{str(y + 1)[-2:]}" for y in range(start - 3, start + 31)}
    try:
        for row in repo.fetch_all("targets"):
            fy = normalize_fy(row.get("financial_year"))
            if fy:
                years.add(fy)
    except Exception:                                   # pragma: no cover
        pass
    return sorted(years, reverse=True)
from ..util import fmt_inr
from .widgets import debounced, fill_table_with_actions, setup_data_table


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
    # Manager was on the client master in v0.3.47 but became redundant
    # once the Sales/Purchase Register Excel began carrying the
    # manager-partner string per voucher line (v0.3.49). The DB column
    # remains for now (migrations only add) — just no longer surfaced.
    TableSpec("clients", "Clients", [
        Field("canonical_name", "Client name"),
        Field("cost_centre_id", "Cost centre", "fk", fk_table="cost_centres",
              optional=True),
    ], order_by="canonical_name"),
    TableSpec("services", "Services", [
        Field("name", "Service name"),
    ], order_by="name"),
    TableSpec("targets", "Annual Targets", [
        Field("financial_year", "Financial year", "fy"),
        Field("cost_centre_id", "Cost centre", "fk", fk_table="cost_centres"),
        Field("target_amount", "Target amount", "float"),
    ], soft_delete=False),
    # The "Fixed Office Overhead" master tab (v0.3.57 → v0.3.68) is gone:
    # office overhead is now computed from the books — Office-cost-centre
    # indirect expenses ÷ active employees (timesheet) per period. The
    # fixed_office_overhead TABLE remains in the DB (migrations only add)
    # but nothing reads it any more.
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
        if f.kind == "fy":
            # Financial-year picker: a dropdown of FYs (current ± a few,
            # plus any already in use). Editable so an out-of-range year
            # can still be typed; the value is normalised on save.
            w = QComboBox()
            w.setEditable(True)
            choices = _fy_choices()
            cur = normalize_fy(current) if current else ""
            if cur and cur not in choices:
                choices.insert(0, cur)
            w.addItems(choices)
            today = _dt.date.today()
            default = cur or financial_year(
                f"{today.year:04d}-{today.month:02d}")
            w.setCurrentText(default)
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
        self.summary = QLabel("")
        self.summary.setObjectName("sectionTitle")
        toolbar.addWidget(self.summary)
        toolbar.addStretch(1)
        if spec.soft_delete:
            self.show_inactive = QCheckBox("Show inactive")
            self.show_inactive.stateChanged.connect(self.reload)
            toolbar.addWidget(self.show_inactive)
        else:
            self.show_inactive = None
        if spec.table == "clients":
            self.import_btn = QPushButton("📁 Import from Excel…")
            self.import_btn.setToolTip(
                "Bulk-import a list of clients with their cost-centre codes "
                "from an Excel file. Expected columns: Client | Cost Centre.")
            self.import_btn.clicked.connect(self._import_clients_from_excel)
            toolbar.addWidget(self.import_btn)
        elif spec.table == "employees":
            self.import_btn = QPushButton("📁 Import from Excel…")
            self.import_btn.setToolTip(
                "Bulk-import a list of employees with their cost-centre "
                "codes from an Excel file. Expected columns: Employee Name "
                "| Cost Centre. Slight name variations in existing salary / "
                "timesheet data get auto-linked at ≥70% confidence.")
            self.import_btn.clicked.connect(self._import_employees_from_excel)
            toolbar.addWidget(self.import_btn)
        self.add_btn = QPushButton(f"＋ Add {spec.title.rstrip('s').lower()}")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self._add)
        toolbar.addWidget(self.add_btn)
        layout.addLayout(toolbar)

        # Search row.
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self._sched_reload, self._search_timer = debounced(self.reload)
        self.search.textChanged.connect(self._sched_reload)
        search_bar.addWidget(self.search)
        layout.addLayout(search_bar)

        self.table = QTableWidget()
        setup_data_table(self.table)
        self.table.doubleClicked.connect(
            lambda idx: self._edit_row(idx.row()))
        layout.addWidget(self.table)

        self._fk_maps = {f.fk_table: repo.fk_label_map(f.fk_table)
                         for f in spec.fields if f.kind == "fk"}
        self.reload()

    def count_active(self) -> int:
        return sum(1 for r in self._rows if r.get("active", 1))

    # -- data ----------------------------------------------------------------
    def reload(self) -> None:
        include_inactive = bool(self.show_inactive and self.show_inactive.isChecked())
        self._fk_maps = {t: repo.fk_label_map(t) for t in self._fk_maps}
        all_rows = repo.fetch_all(
            self.spec.table, include_inactive=include_inactive,
            order_by=self.spec.order_by)
        # Apply text search across every visible field on each row.
        q = self.search.text().strip().lower()
        if q:
            def matches(row):
                for f in self.spec.fields:
                    val = self._display(f, row).lower()
                    if q in val:
                        return True
                return False
            self._rows = [r for r in all_rows if matches(r)]
        else:
            self._rows = all_rows
        active = self.count_active()
        total = len(all_rows)
        showing = len(self._rows)
        if total == 0:
            summary = "No records yet"
        elif showing == total:
            summary = f"{active} record{'s' if active != 1 else ''}"
            if total > active:
                summary += f"  ·  {total - active} inactive shown"
        else:
            summary = f"{showing} of {total} match{'es' if showing != 1 else ''}"
        self.summary.setText(summary)
        self._render()

    def _render(self) -> None:
        headers = [f.label for f in self.spec.fields]
        body_rows = []
        for row in self._rows:
            body = [self._display(f, row) for f in self.spec.fields]
            body_rows.append(body)

        def status_for(i: int):
            if not self.spec.soft_delete:
                return ("Active", "statusOk")
            return (("Active", "statusOk")
                    if self._rows[i].get("active", 1)
                    else ("Inactive", "statusMuted"))

        if not body_rows:
            self.table.setRowCount(0)
            return

        action_label = []
        for r in self._rows:
            if self.spec.soft_delete:
                action_label.append("Activate"
                                    if not r.get("active", 1) else "Edit")
            else:
                action_label.append("Edit")

        secondary_label = None
        secondary_callback = None
        secondary_object_name = "rowAction"
        if self.spec.soft_delete:
            secondary_label = "Deactivate"
            secondary_callback = self._deactivate_row
            secondary_object_name = "rowActionDanger"
        else:
            secondary_label = "Delete"
            secondary_callback = self._delete_row
            secondary_object_name = "rowActionDanger"

        fill_table_with_actions(
            self.table, headers, body_rows,
            action_label=action_label,
            action_callback=self._edit_row,
            secondary_label=secondary_label,
            secondary_callback=secondary_callback,
            secondary_object_name=secondary_object_name,
            status_for_row=status_for,
            stretch_col=0,
        )

    def _display(self, f: Field, row: dict[str, Any]) -> str:
        value = row.get(f.key)
        if value in (None, ""):
            return ""
        if f.kind == "fk":
            return self._fk_maps.get(f.fk_table, {}).get(value, f"#{value}")
        if f.kind == "float":
            return fmt_inr(value, 2)
        return str(value)

    # -- actions -------------------------------------------------------------
    def _normalize_values(self, values: dict[str, Any]) -> dict[str, Any]:
        """Canonicalise operator input before persisting. Currently the
        Targets master's loosely-typed financial year ('2026 - 27' →
        '2026-27') so it matches the form the MIS computes from periods."""
        if self.spec.table == "targets" and "financial_year" in values:
            values["financial_year"] = normalize_fy(values["financial_year"])
        return values

    def _add(self) -> None:
        dlg = RecordDialog(self.spec, None, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = self._normalize_values(dlg.values())
                new_id = repo.insert(self.spec.table, values)
            except Exception as exc:  # e.g. UNIQUE violation
                QMessageBox.critical(self, "Could not add", str(exc))
            else:
                self._post_save_repoint(new_id, values)
            self.reload()

    def _import_clients_from_excel(self) -> None:
        self._import_name_cc_pairs_from_excel(
            title="Import Clients from Excel",
            name_synonyms=("client",),
            descriptor="Client",
            kind_label="clients",
            service=resolution.bulk_import_clients,
        )

    def _import_employees_from_excel(self) -> None:
        self._import_name_cc_pairs_from_excel(
            title="Import Employees from Excel",
            name_synonyms=("employee name", "employee", "name"),
            descriptor="Employee Name",
            kind_label="employees",
            service=resolution.bulk_import_employees,
            extra_summary=lambda r: (
                [f"Raw names linked to master via fuzzy match: "
                 f"{r.get('newly_aliased', 0)}"]
                if r.get("newly_aliased") else []),
        )

    def _import_name_cc_pairs_from_excel(
            self, *, title: str,
            name_synonyms: tuple[str, ...],
            descriptor: str, kind_label: str,
            service, extra_summary=None) -> None:
        """Shared workflow: pick an Excel, extract (name, cc_code) rows
        from a header row, hand to a bulk-import service, show summary."""
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "Excel files (*.xlsx *.xls)")
        if not path:
            return
        try:
            grid = excel_reader.read_grid(path)
        except Exception as exc:
            QMessageBox.critical(
                self, "Couldn't read file", f"Could not read {path}:\n\n{exc}")
            return
        pairs = self._extract_name_cc_pairs(grid, name_synonyms)
        if not pairs:
            QMessageBox.warning(
                self, "No data found",
                f"Couldn't find a '{descriptor}' + 'Cost Centre' header row "
                f"in this file. Make sure the first two columns are named "
                f"'{descriptor}' and 'Cost Centre' (case-insensitive).")
            return
        msg = (f"Found {len(pairs)} {kind_label} → cost-centre rows in this "
               "file.\n\nExisting rows keep any cost-centre already "
               "assigned; rows whose cost-centre is unset will be filled "
               "in. New rows are created.\n\nContinue?")
        if QMessageBox.question(self, f"Import {kind_label}?", msg) \
                != QMessageBox.Yes:
            return
        report = service(pairs, overwrite_existing_cc=False)
        lines = [
            f"Total rows processed: {report['rows_total']}",
            f"New {kind_label} created: {report['created']}",
            f"Existing rows whose cost-centre got filled in: "
            f"{report['cc_set']}",
            f"Existing rows unchanged (already had the same CC): "
            f"{report['unchanged']}",
        ]
        if extra_summary:
            lines.extend(extra_summary(report))
        if report["unknown_cc"]:
            lines.append(
                f"\nSkipped {len(report['unknown_cc'])} row(s) with unknown "
                "cost-centre codes (not in master). First few:")
            for name, code in report["unknown_cc"][:10]:
                lines.append(f"  • {name} → {code!r}")
        QMessageBox.information(self, "Import complete", "\n".join(lines))
        self.reload()

    @staticmethod
    def _extract_name_cc_pairs(
            grid: list[list],
            name_synonyms: tuple[str, ...]) -> list[tuple[str, str]]:
        """Find the (name, cost-centre) header row + return data tuples."""
        header_row = -1
        name_col = cc_col = -1
        cc_synonyms = ("cost centre", "cost center", "cc")
        for r_idx, row in enumerate(grid[:20]):
            cells = [(str(c).strip().lower() if c is not None else "")
                     for c in row]
            for i, txt in enumerate(cells):
                if txt in name_synonyms:
                    name_col = i
                elif txt in cc_synonyms:
                    cc_col = i
            if name_col >= 0 and cc_col >= 0:
                header_row = r_idx
                break
            name_col = cc_col = -1
        if header_row < 0:
            return []
        out: list[tuple[str, str]] = []
        for row in grid[header_row + 1:]:
            if not row:
                continue
            name = row[name_col] if name_col < len(row) else None
            code = row[cc_col] if cc_col < len(row) else None
            name_s = (str(name).strip() if name is not None else "")
            code_s = (str(code).strip() if code is not None else "")
            if name_s and code_s:
                out.append((name_s, code_s))
        return out

    def _edit_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        record = self._rows[idx]
        # If the row is inactive in a soft-delete table, "Activate" replaces
        # the edit dialog.
        if self.spec.soft_delete and not record.get("active", 1):
            repo.set_active(self.spec.table, record["id"], True)
            self.reload()
            return
        dlg = RecordDialog(self.spec, record, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = self._normalize_values(dlg.values())
                repo.update(self.spec.table, record["id"], values)
            except Exception as exc:
                QMessageBox.critical(self, "Could not save", str(exc))
            else:
                self._post_save_repoint(record["id"], values)
            self.reload()

    def _post_save_repoint(self, row_id: int,
                            values: dict[str, Any]) -> None:
        """After adding / editing a client or employee master row, force
        any stale voucher / timesheet links whose raw name matches the
        new canonical name to point at this row.

        Without this, an earlier wrong fuzzy or Review-dialog link
        persists in the data even after the operator manually creates
        the correct master row (the symptom: 'I added Bilimoria Mehta
        & Co as a client but the salary sheet still shows Dinaz Mehta
        for the firm's own internal time').
        """
        if self.spec.table == "clients":
            name = (values.get("canonical_name") or "").strip()
            if name:
                resolution.repoint_client_links(int(row_id), name)
        elif self.spec.table == "employees":
            name = (values.get("name") or "").strip()
            if name:
                resolution.repoint_employee_links(int(row_id), name)

    def _deactivate_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        record = self._rows[idx]
        if QMessageBox.question(
                self, "Deactivate",
                "Deactivate this record? Existing history that references it "
                "is preserved; you won't see it in dropdowns going forward."
                ) == QMessageBox.Yes:
            repo.set_active(self.spec.table, record["id"], False)
            self.reload()

    def _delete_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        record = self._rows[idx]
        if QMessageBox.question(
                self, "Delete permanently",
                "Delete this record permanently? This cannot be undone."
                ) == QMessageBox.Yes:
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
        self._refresh_badges()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._refresh_badges()

    def _refresh_current(self, index: int) -> None:
        # FK dropdowns may have changed on another tab — reload on switch.
        if 0 <= index < len(self._tabs):
            self._tabs[index].reload()
        self._refresh_badges()

    def _refresh_badges(self) -> None:
        for i, tab in enumerate(self._tabs):
            base = tab.spec.title
            n = tab.count_active()
            self.tabs.setTabText(i, f"{base}  ({n})" if n else base)
