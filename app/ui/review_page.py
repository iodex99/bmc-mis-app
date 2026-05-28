"""Review & Map page — resolve unknown clients/employees and edit splits."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, repository as repo
from ..services import resolution
from ..services import vouchers as vsvc
from ..util import fmt_inr
from .review_dialogs import (
    ResolveClientDialog,
    ResolveEmployeeDialog,
    SplitEditorDialog,
)


def _fill(table: QTableWidget, headers: list[str], rows: list[list]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)


# --- Client resolution tab ---------------------------------------------------

class ClientTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.info = QLabel()
        auto_btn = QPushButton("Auto-resolve known")
        bulk_btn = QPushButton("Create all as new clients")
        resolve_btn = QPushButton("Resolve selected…")
        auto_btn.clicked.connect(self._auto)
        bulk_btn.clicked.connect(self._bulk)
        resolve_btn.clicked.connect(self._resolve)
        bar.addWidget(self.info)
        bar.addStretch(1)
        bar.addWidget(auto_btn)
        bar.addWidget(bulk_btn)
        bar.addWidget(resolve_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._resolve)
        layout.addWidget(self.table)

    def reload(self) -> None:
        self._rows = resolution.unresolved_clients()
        _fill(self.table, ["Raw client name", "Seen in", "Rows"],
              [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
               for r in self._rows])
        n = len(self._rows)
        self.info.setText("All clients resolved ✓" if n == 0
                          else f"{n} unresolved client name(s)")

    def _auto(self) -> None:
        linked = resolution.apply_known_client_aliases()
        QMessageBox.information(self, "Auto-resolve",
                                f"{linked} row(s) linked via known names.")
        self.reload()

    def _bulk(self) -> None:
        if not self._rows:
            return
        if QMessageBox.question(
                self, "Create all as new clients",
                f"Create {len(self._rows)} new client record(s) from the raw "
                "names (cost centre left unassigned)?\n\nYou can set cost "
                "centres afterwards in Master Data.") != QMessageBox.Yes:
            return
        n = resolution.bulk_create_clients()
        QMessageBox.information(self, "Done", f"{n} client(s) created.")
        self.reload()

    def _resolve(self) -> None:
        sel = {i.row() for i in self.table.selectedIndexes()}
        if not sel:
            return
        raw = self._rows[sel.pop()]["raw"]
        dlg = ResolveClientDialog(raw, self)
        if dlg.exec() == ResolveClientDialog.Accepted:
            dlg.apply()
            self.reload()


# --- Employee resolution tab -------------------------------------------------

class EmployeeTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.info = QLabel()
        bulk_btn = QPushButton("Create all as new employees")
        resolve_btn = QPushButton("Resolve selected…")
        bulk_btn.clicked.connect(self._bulk)
        resolve_btn.clicked.connect(self._resolve)
        bar.addWidget(self.info)
        bar.addStretch(1)
        bar.addWidget(bulk_btn)
        bar.addWidget(resolve_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._resolve)
        layout.addWidget(self.table)

    def reload(self) -> None:
        self._rows = resolution.unresolved_employees()
        _fill(self.table, ["Raw employee name", "Seen in", "Rows"],
              [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
               for r in self._rows])
        n = len(self._rows)
        self.info.setText("All employees resolved ✓" if n == 0
                          else f"{n} unresolved employee name(s)")

    def _bulk(self) -> None:
        if not self._rows:
            return
        if QMessageBox.question(
                self, "Create all as new employees",
                f"Create {len(self._rows)} new employee record(s) from the raw "
                "names (manager and cost centre left blank)?\n\nYou can set "
                "those afterwards in Master Data.") != QMessageBox.Yes:
            return
        n = resolution.bulk_create_employees()
        QMessageBox.information(self, "Done", f"{n} employee(s) created.")
        self.reload()

    def _resolve(self) -> None:
        sel = {i.row() for i in self.table.selectedIndexes()}
        if not sel:
            return
        raw = self._rows[sel.pop()]["raw"]
        dlg = ResolveEmployeeDialog(raw, self)
        if dlg.exec() == ResolveEmployeeDialog.Accepted:
            dlg.apply()
            self.reload()


# --- Voucher review tab ------------------------------------------------------

class VoucherTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.entity_combo = QComboBox()
        self.period_combo = QComboBox()
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("All", None)
        self.kind_combo.addItem("Sales", config.VCH_SALES)
        self.kind_combo.addItem("Expenses", config.VCH_EXPENSE)
        for w in (self.entity_combo, self.period_combo, self.kind_combo):
            w.currentIndexChanged.connect(self.reload)
        edit_btn = QPushButton("Edit splits…")
        edit_btn.clicked.connect(self._edit)
        bar.addWidget(QLabel("Entity:"))
        bar.addWidget(self.entity_combo)
        bar.addWidget(QLabel("Period:"))
        bar.addWidget(self.period_combo)
        bar.addWidget(QLabel("Kind:"))
        bar.addWidget(self.kind_combo)
        bar.addStretch(1)
        bar.addWidget(edit_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)

        self._loading = False
        self._reload_filters()

    def _reload_filters(self) -> None:
        self._loading = True
        for combo, items in (
            (self.entity_combo, [("(all)", None)] + repo.fk_options("entities")),
            (self.period_combo, [("(all)", None)] +
             [(p, p) for p in vsvc.list_periods()]),
        ):
            keep = combo.currentData()
            combo.clear()
            for label, data in items:
                combo.addItem(str(label), data)
            pos = combo.findData(keep)
            if pos >= 0:
                combo.setCurrentIndex(pos)
        self._loading = False
        self.reload()

    def reload(self) -> None:
        if self._loading:
            return
        self._rows = vsvc.list_vouchers(
            self.entity_combo.currentData(),
            self.period_combo.currentData(),
            self.kind_combo.currentData())
        out = []
        for v in self._rows:
            if v["n_unassigned"]:
                splits = f"⚠ {v['n_unassigned']} unassigned"
            else:
                splits = f"{v['n_splits']} split(s)"
            out.append([v["txn_date"] or "", v["vch_no"], v["party_name"],
                        v["client_name"] or "—", v["kind"],
                        fmt_inr(v['net_amount'], 2), splits])
        _fill(self.table, ["Date", "Vch No.", "Party", "Client", "Kind",
                           "Net Amount", "Splits"], out)

    def _edit(self) -> None:
        sel = {i.row() for i in self.table.selectedIndexes()}
        if not sel:
            return
        voucher = self._rows[sel.pop()]
        dlg = SplitEditorDialog(voucher, self)
        if dlg.exec() == SplitEditorDialog.Accepted:
            self.reload()


# --- The page ----------------------------------------------------------------

class ReviewPage(QWidget):
    """Hosts the client, employee and voucher review tabs."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel("Review & Map")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        note = QLabel("Resolve unknown clients and employees, and split / "
                      "attribute vouchers to 'Partner – Manager' strings.")
        note.setObjectName("pageNote")
        layout.addWidget(note)

        self.tabs = QTabWidget()
        self.client_tab = ClientTab()
        self.employee_tab = EmployeeTab()
        self.voucher_tab = VoucherTab()
        self.tabs.addTab(self.client_tab, "Clients")
        self.tabs.addTab(self.employee_tab, "Employees")
        self.tabs.addTab(self.voucher_tab, "Vouchers & Splits")
        self.tabs.currentChanged.connect(self._refresh)
        layout.addWidget(self.tabs)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        resolution.apply_known_client_aliases()
        self._refresh(self.tabs.currentIndex())

    def _refresh(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if index == 2:
            self.voucher_tab._reload_filters()
        elif hasattr(widget, "reload"):
            widget.reload()
