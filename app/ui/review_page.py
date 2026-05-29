"""Review & Map page — resolve unknown clients/employees and edit splits."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, repository as repo
from ..services import resolution
from ..services import vouchers as vsvc
from ..util import fmt_inr
from .review_dialogs import (
    ResolveCcStringDialog,
    ResolveClientDialog,
    ResolveEmployeeDialog,
    SplitEditorDialog,
)
from .widgets import (
    NoScrollComboBox,
    fill_table_with_actions,
    setup_data_table,
)


def _warn_pill(_: int) -> tuple[str, str]:
    return "Unmapped", "statusWarn"


def _empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("emptyState")
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    return label


# --- Client tab --------------------------------------------------------------

class ClientTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "These client names appeared in your files but aren't linked to "
            "your master list yet. Click <b>Resolve →</b> on each row to "
            "match it to an existing client or create a new one.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        auto_btn = QPushButton("⚡ Auto-resolve known")
        bulk_btn = QPushButton("➕ Create all as new")
        auto_btn.clicked.connect(self._auto)
        bulk_btn.clicked.connect(self._bulk)
        bar.addWidget(auto_btn)
        bar.addWidget(bulk_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        setup_data_table(self.table)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        layout.addWidget(self.table, 1)

        self.empty = _empty_state(
            "✓  Every client name is mapped.<br>"
            "<span style='color:#64748B;'>Once you import more files, any new "
            "names will show up here.</span>")
        self.empty.setVisible(False)
        layout.addWidget(self.empty, 1)

    def count(self) -> int:
        return len(self._rows)

    def reload(self) -> None:
        # Always re-apply known aliases first — picks up newly-imported rows.
        resolution.apply_known_client_aliases()
        self._rows = resolution.unresolved_clients()
        n = len(self._rows)
        self.info.setText(
            "All clients mapped" if n == 0
            else f"{n} client name{'s' if n != 1 else ''} need mapping")
        self.empty.setVisible(n == 0)
        self.table.setVisible(n > 0)
        if n:
            rows = [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
                    for r in self._rows]
            fill_table_with_actions(
                self.table,
                ["Raw client name", "Seen in", "Rows"],
                rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                status_for_row=_warn_pill,
                stretch_col=0,
            )

    def _auto(self) -> None:
        n = resolution.apply_known_client_aliases()
        QMessageBox.information(
            self, "Auto-resolve",
            f"{n} row(s) linked using previously saved names.")
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

    def _resolve_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        raw = self._rows[idx]["raw"]
        dlg = ResolveClientDialog(raw, self)
        if dlg.exec() == ResolveClientDialog.Accepted:
            dlg.apply()
            self.reload()


# --- Employee tab ------------------------------------------------------------

class EmployeeTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Employees seen in the timesheet or salary sheet that don't yet "
            "have a master record. Resolve each row to assign their manager "
            "and cost centre.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        bulk_btn = QPushButton("➕ Create all as new")
        bulk_btn.clicked.connect(self._bulk)
        bar.addWidget(bulk_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        setup_data_table(self.table)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        layout.addWidget(self.table, 1)

        self.empty = _empty_state(
            "✓  Every employee is mapped.<br>"
            "<span style='color:#64748B;'>New employees from future timesheet "
            "/ salary imports will appear here.</span>")
        self.empty.setVisible(False)
        layout.addWidget(self.empty, 1)

    def count(self) -> int:
        return len(self._rows)

    def reload(self) -> None:
        self._rows = resolution.unresolved_employees()
        n = len(self._rows)
        self.info.setText(
            "All employees mapped" if n == 0
            else f"{n} employee name{'s' if n != 1 else ''} need mapping")
        self.empty.setVisible(n == 0)
        self.table.setVisible(n > 0)
        if n:
            rows = [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
                    for r in self._rows]
            fill_table_with_actions(
                self.table,
                ["Raw employee name", "Seen in", "Rows"],
                rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                status_for_row=_warn_pill,
                stretch_col=0,
            )

    def _bulk(self) -> None:
        if not self._rows:
            return
        if QMessageBox.question(
                self, "Create all as new employees",
                f"Create {len(self._rows)} new employee record(s)?\n\n"
                "Manager and cost centre are left blank — you can fill them "
                "in afterwards in Master Data.") != QMessageBox.Yes:
            return
        n = resolution.bulk_create_employees()
        QMessageBox.information(self, "Done", f"{n} employee(s) created.")
        self.reload()

    def _resolve_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        raw = self._rows[idx]["raw"]
        dlg = ResolveEmployeeDialog(raw, self)
        if dlg.exec() == ResolveEmployeeDialog.Accepted:
            dlg.apply()
            self.reload()


# --- Cost-centre string tab --------------------------------------------------

class CcStringTab(QWidget):
    """Resolve raw Tally Cost Centre strings to (partner, manager) pairs."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Tally's <b>Cost Center</b> column carries the partner / manager "
            "behind each invoice. Map each distinct string to a partner (and "
            "optionally a manager) — the mapping is remembered, so future "
            "imports auto-resolve.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        auto_btn = QPushButton("⚡ Re-apply known")
        auto_btn.clicked.connect(self._auto)
        bar.addWidget(auto_btn)
        layout.addLayout(bar)

        self.table = QTableWidget()
        setup_data_table(self.table)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        layout.addWidget(self.table, 1)

        self.empty = _empty_state(
            "✓  Every Cost Centre string is mapped.<br>"
            "<span style='color:#64748B;'>Tally invoices route to the right "
            "partner automatically.</span>")
        self.empty.setVisible(False)
        layout.addWidget(self.empty, 1)

    def count(self) -> int:
        return len(self._rows)

    def reload(self) -> None:
        resolution.apply_known_cc_string_mappings()
        self._rows = resolution.unresolved_cc_strings()
        n = len(self._rows)
        self.info.setText(
            "All Cost Centre strings mapped" if n == 0
            else f"{n} Cost Centre string{'s' if n != 1 else ''} need mapping")
        self.empty.setVisible(n == 0)
        self.table.setVisible(n > 0)
        if n:
            rows = [[r["raw"], r["count"]] for r in self._rows]
            fill_table_with_actions(
                self.table, ["Cost Centre string", "Invoices"], rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                status_for_row=_warn_pill,
                stretch_col=0,
            )

    def _auto(self) -> None:
        n = resolution.apply_known_cc_string_mappings()
        QMessageBox.information(
            self, "Re-apply", f"{n} voucher split(s) updated from saved mappings.")
        self.reload()

    def _resolve_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        raw = self._rows[idx]["raw"]
        dlg = ResolveCcStringDialog(raw, self)
        if dlg.exec() == ResolveCcStringDialog.Accepted:
            dlg.apply()
            self.reload()


# --- Voucher review tab ------------------------------------------------------

class VoucherTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Every voucher's amount can be split across cost centres, "
            "managers and services. Use the filters to find what you need; "
            "click <b>Edit splits →</b> on any row to adjust its attribution.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.entity_combo = NoScrollComboBox()
        self.period_combo = NoScrollComboBox()
        self.kind_combo = NoScrollComboBox()
        self.kind_combo.addItem("All", None)
        self.kind_combo.addItem("Sales", config.VCH_SALES)
        self.kind_combo.addItem("Expenses", config.VCH_EXPENSE)
        for w in (self.entity_combo, self.period_combo, self.kind_combo):
            w.currentIndexChanged.connect(self.reload)
        bar.addWidget(QLabel("Entity:"))
        bar.addWidget(self.entity_combo)
        bar.addWidget(QLabel("Period:"))
        bar.addWidget(self.period_combo)
        bar.addWidget(QLabel("Kind:"))
        bar.addWidget(self.kind_combo)
        bar.addStretch(1)
        self.summary = QLabel("")
        self.summary.setObjectName("sectionTitle")
        bar.addWidget(self.summary)
        layout.addLayout(bar)

        self.table = QTableWidget()
        setup_data_table(self.table)
        self.table.doubleClicked.connect(
            lambda idx: self._edit_row(idx.row()))
        layout.addWidget(self.table, 1)

        self.empty = _empty_state(
            "No vouchers match these filters yet.<br>"
            "<span style='color:#64748B;'>Try a different period or import "
            "more files.</span>")
        self.empty.setVisible(False)
        layout.addWidget(self.empty, 1)

        self._reload_filters()

    def count(self) -> int:
        # The badge shows vouchers still needing attention (unassigned splits).
        return sum(1 for v in self._rows if v.get("n_unassigned"))

    def _reload_filters(self) -> None:
        self._loading = True
        for combo, items in (
            (self.entity_combo,
             [("(all entities)", None)] + repo.fk_options("entities")),
            (self.period_combo,
             [("(all periods)", None)] +
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
        n = len(self._rows)
        unassigned = self.count()
        if unassigned:
            self.summary.setText(
                f"{n} voucher{'s' if n != 1 else ''}  ·  "
                f"<span style='color:#B91C1C;'>{unassigned} unassigned</span>")
        else:
            self.summary.setText(f"{n} voucher{'s' if n != 1 else ''}")
        self.empty.setVisible(n == 0)
        self.table.setVisible(n > 0)

        if n == 0:
            return

        rows = []
        labels = []
        for v in self._rows:
            rows.append([
                v["txn_date"] or "",
                v["vch_no"], v["party_name"],
                v["client_name"] or "—",
                v["kind"].capitalize(),
                fmt_inr(v["net_amount"], 0),
                (f"⚠ {v['n_unassigned']} unassigned"
                 if v["n_unassigned"] else f"{v['n_splits']} split(s)"),
            ])
            labels.append("Edit splits →")

        def status_for(i):
            return ("Needs fix" if self._rows[i]["n_unassigned"]
                    else "OK"), \
                ("statusWarn" if self._rows[i]["n_unassigned"]
                    else "statusOk")

        fill_table_with_actions(
            self.table,
            ["Date", "Vch No.", "Party", "Client", "Kind",
             "Net amount", "Splits"],
            rows,
            action_label=labels,
            action_callback=self._edit_row,
            status_for_row=status_for,
            stretch_col=2,
        )

    def _edit_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        voucher = self._rows[idx]
        dlg = SplitEditorDialog(voucher, self)
        if dlg.exec() == SplitEditorDialog.Accepted:
            self.reload()


# --- the page ----------------------------------------------------------------

_TAB_BASE_NAMES = ["Clients", "Employees", "Cost Centres", "Vouchers"]


class ReviewPage(QWidget):
    """Hosts the client, employee, cc-string and voucher review tabs."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel("Review & Map")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        note = QLabel(
            "Resolve unknown clients, employees and Cost Centre strings, "
            "then split / attribute vouchers across partners and services.")
        note.setObjectName("pageNote")
        layout.addWidget(note)

        self.tabs = QTabWidget()
        self.client_tab = ClientTab()
        self.employee_tab = EmployeeTab()
        self.cc_tab = CcStringTab()
        self.voucher_tab = VoucherTab()
        self.tabs.addTab(self.client_tab, _TAB_BASE_NAMES[0])
        self.tabs.addTab(self.employee_tab, _TAB_BASE_NAMES[1])
        self.tabs.addTab(self.cc_tab, _TAB_BASE_NAMES[2])
        self.tabs.addTab(self.voucher_tab, _TAB_BASE_NAMES[3])
        self.tabs.currentChanged.connect(self._refresh)
        layout.addWidget(self.tabs, 1)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        # Apply saved mappings first so badges show accurate counts.
        resolution.apply_known_client_aliases()
        resolution.apply_known_cc_string_mappings()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "reload"):
                tab.reload()
        self._refresh_badges()

    def _refresh(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.voucher_tab:
            self.voucher_tab._reload_filters()
        elif hasattr(widget, "reload"):
            widget.reload()
        self._refresh_badges()

    def _refresh_badges(self) -> None:
        for i, name in enumerate(_TAB_BASE_NAMES):
            tab = self.tabs.widget(i)
            n = tab.count() if hasattr(tab, "count") else 0
            label = f"{name}  ({n})" if n else name
            self.tabs.setTabText(i, label)
