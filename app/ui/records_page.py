"""Records page — read-only browser into every imported row.

Lets the operator see what's stored — every salary record, every timesheet
line, every import batch — period-tagged and searchable. Also exposes a
per-batch delete so a wrong import can be undone without nuking everything.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import repository as repo
from ..services import records
from ..util import fmt_inr
from .widgets import (
    NoScrollComboBox,
    fill_table_with_actions,
    setup_data_table,
)


_PAGE_LIMIT = 2000


def _info(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageNote")
    label.setWordWrap(True)
    return label


def _debounce(callback, *, ms: int = 250):
    """Return a function that calls *callback* once after *ms* of quiet."""
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(ms)
    timer.timeout.connect(callback)

    def trigger(*_args):
        timer.start()
    return trigger, timer


# --- Imports tab ------------------------------------------------------------

class ImportsTab(QWidget):
    """Lists every import batch with a delete action per row."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(_hint(
            "Every file you've ever imported is listed here. Click "
            "<b>Delete</b> on a row to undo that import — every voucher, "
            "timesheet line or salary row it created is removed; the saved "
            "column-mapping templates and master records you created are "
            "preserved."))

        self.summary = _info("")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        setup_data_table(self.table)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        self._rows = records.list_import_batches()
        ent = repo.fk_label_map("entities")
        body = []
        for b in self._rows:
            rows_total = ((b["vch"] or 0) + (b["ts"] or 0)
                          + (b["sal"] or 0) + (b.get("reim") or 0))
            body.append([
                b["id"],
                b["imported_at"][:16] if b["imported_at"] else "",
                ent.get(b["entity_id"], "—"),
                b["file_type"].capitalize(),
                b["period"] or "—",
                b["file_name"] or "",
                f"{fmt_inr(rows_total)} row{'s' if rows_total != 1 else ''}",
            ])
        self.summary.setText(
            f"{len(self._rows)} import batch{'es' if len(self._rows) != 1 else ''}")
        fill_table_with_actions(
            self.table,
            ["#", "Imported", "Entity", "Type", "Period", "File", "Rows"],
            body,
            action_label="Delete",
            action_callback=self._delete,
            secondary_object_name="rowActionDanger",
            stretch_col=5,
        )

    def _delete(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        b = self._rows[idx]
        rows_total = ((b["vch"] or 0) + (b["ts"] or 0)
                          + (b["sal"] or 0) + (b.get("reim") or 0))
        confirm = QMessageBox.warning(
            self, "Delete import?",
            f"This will permanently delete batch #{b['id']} "
            f"({b['file_type']} for {b['period'] or 'unknown period'}, "
            f"{rows_total} row(s)).\n\nThe rows it created are removed; "
            "any client / employee / cost-centre records you mapped or "
            "created are kept.\n\nContinue?",
            QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel)
        if confirm != QMessageBox.Yes:
            return
        try:
            records.delete_import_batch(b["id"])
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return
        self.reload()


# --- Salary tab -------------------------------------------------------------

class SalaryTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._first_load = True
        self._show_all = False
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_hint(
            "Every salary row imported across every period. Defaults to the "
            "latest month — switch the dropdown to a different period or "
            "'(all periods)' to compare months side by side."))

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(QLabel("Period:"))
        self.period_combo = NoScrollComboBox()
        self.period_combo.currentIndexChanged.connect(self._on_period_change)
        bar.addWidget(self.period_combo)
        bar.addWidget(QLabel("Employee:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("filter by name…")
        self._sched_reload, self._search_timer = _debounce(self.reload)
        self.search.textChanged.connect(self._sched_reload)
        bar.addWidget(self.search, 1)
        layout.addLayout(bar)

        self.summary = _info("")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        setup_data_table(self.table)
        layout.addWidget(self.table, 1)

        self.load_all_btn = QPushButton("")
        self.load_all_btn.setVisible(False)
        self.load_all_btn.clicked.connect(self._load_all)
        layout.addWidget(self.load_all_btn, alignment=Qt.AlignLeft)

    def _on_period_change(self):
        # Switching period resets the show_all override.
        self._show_all = False
        self.reload()

    def _load_all(self):
        self._show_all = True
        self.reload()

    def reload(self) -> None:
        self._refill_periods()
        period = self.period_combo.currentData()
        q = self.search.text().strip()
        limit = None if self._show_all else _PAGE_LIMIT
        rows = records.list_salary(period, q, limit=limit)
        totals = records.salary_totals(period, q)
        total_n = totals.get("n", 0)
        showing = len(rows)
        truncated = (not self._show_all) and total_n > showing

        msg = (f"{fmt_inr(total_n)} row(s) · "
               f"{fmt_inr(totals.get('people', 0))} employee(s) · "
               f"Salary ₹ {fmt_inr(totals.get('salary', 0))} · "
               f"Reimbursement ₹ {fmt_inr(totals.get('reimb', 0))}")
        if truncated:
            msg += (f"   <span style='color:#92400E;'>"
                    f"(showing first {fmt_inr(showing)})</span>")
        self.summary.setText(msg)
        self.load_all_btn.setVisible(truncated)
        self.load_all_btn.setText(
            f"Load all {fmt_inr(total_n)} row(s)" if truncated else "")

        body = [[
            r["period"] or "",
            r["employee_name"] or "",
            f"{r['cc_code']} — {r['cc_name']}" if r["cc_code"] else "—",
            r["entity_name"] or "—",
            r["category"] or "",
            fmt_inr(r["salary_paid"] or 0, 2),
            fmt_inr(r["reimbursement"] or 0, 2),
        ] for r in rows]
        fill_table_with_actions(
            self.table,
            ["Period", "Employee", "Cost centre", "Entity", "Category",
             "Salary paid", "Reimbursement"],
            body, stretch_col=1,
        )

    def _refill_periods(self) -> None:
        keep = self.period_combo.currentData()
        periods = records.list_salary_periods()
        self.period_combo.blockSignals(True)
        self.period_combo.clear()
        self.period_combo.addItem("(all periods)", None)
        for p in periods:
            self.period_combo.addItem(p, p)
        # First load: default to the most recent period. Otherwise preserve.
        if self._first_load and periods:
            idx = self.period_combo.findData(periods[0])
            if idx >= 0:
                self.period_combo.setCurrentIndex(idx)
            self._first_load = False
        elif keep is not None:
            idx = self.period_combo.findData(keep)
            if idx >= 0:
                self.period_combo.setCurrentIndex(idx)
        self.period_combo.blockSignals(False)


# --- Timesheet tab ----------------------------------------------------------

class TimesheetTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._first_load = True
        self._show_all = False
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_hint(
            "Every timesheet line, bucketed into the MIS month it "
            "contributes to. The firm's timesheet cycle runs <b>21st of "
            "the previous month → 20th of the current month</b>, so a row "
            "from 25 Dec shows up under <b>2026-01</b> (January MIS). "
            "Defaults to the latest period — switch the dropdown to a "
            "different period or '(all periods)' to compare."))

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(QLabel("Period:"))
        self.period_combo = NoScrollComboBox()
        self.period_combo.currentIndexChanged.connect(self._on_period_change)
        bar.addWidget(self.period_combo)
        bar.addWidget(QLabel("Employee:"))
        self.emp_search = QLineEdit()
        self.emp_search.setPlaceholderText("filter by name…")
        bar.addWidget(self.emp_search, 1)
        bar.addWidget(QLabel("Client:"))
        self.client_search = QLineEdit()
        self.client_search.setPlaceholderText("filter by client…")
        bar.addWidget(self.client_search, 1)
        self._sched_reload, self._timer = _debounce(self.reload)
        self.emp_search.textChanged.connect(self._sched_reload)
        self.client_search.textChanged.connect(self._sched_reload)
        layout.addLayout(bar)

        self.summary = _info("")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        setup_data_table(self.table)
        layout.addWidget(self.table, 1)

        self.load_all_btn = QPushButton("")
        self.load_all_btn.setVisible(False)
        self.load_all_btn.clicked.connect(self._load_all)
        layout.addWidget(self.load_all_btn, alignment=Qt.AlignLeft)

    def _on_period_change(self):
        self._show_all = False
        self.reload()

    def _load_all(self):
        self._show_all = True
        self.reload()

    def reload(self) -> None:
        self._refill_periods()
        period = self.period_combo.currentData()
        emp_q = self.emp_search.text().strip()
        cli_q = self.client_search.text().strip()
        limit = None if self._show_all else _PAGE_LIMIT
        rows = records.list_timesheet(period, emp_q, cli_q, limit=limit)
        totals = records.timesheet_totals(period, emp_q, cli_q)
        total_n = totals.get("n", 0)
        showing = len(rows)
        truncated = (not self._show_all) and total_n > showing

        msg = (f"{fmt_inr(total_n)} row(s) · "
               f"{fmt_inr(totals.get('people', 0))} employee(s) · "
               f"{fmt_inr(totals.get('clients', 0))} client(s) · "
               f"{fmt_inr(totals.get('hours', 0), 1)} hours "
               f"({fmt_inr(totals.get('billable_hours', 0), 1)} billable)")
        if truncated:
            msg += (f"   <span style='color:#92400E;'>"
                    f"(showing first {fmt_inr(showing)})</span>")
        self.summary.setText(msg)
        self.load_all_btn.setVisible(truncated)
        self.load_all_btn.setText(
            f"Load all {fmt_inr(total_n)} row(s)" if truncated else "")

        body = [[
            (r["txn_date"] or "")[:10],
            r["emp_name"] or "",
            r["client_name"] or r["client_raw"] or "—",
            r["task"] or "",
            fmt_inr(r["hours"] or 0, 2),
            r["reporting_manager"] or "",
            "Yes" if r["is_billable"] else "No",
        ] for r in rows]
        fill_table_with_actions(
            self.table,
            ["Date", "Employee", "Client", "Task", "Hours", "Manager",
             "Billable"],
            body, stretch_col=2,
        )

    def _refill_periods(self) -> None:
        keep = self.period_combo.currentData()
        periods = records.list_timesheet_periods()
        self.period_combo.blockSignals(True)
        self.period_combo.clear()
        self.period_combo.addItem("(all periods)", None)
        for p in periods:
            self.period_combo.addItem(p, p)
        if self._first_load and periods:
            idx = self.period_combo.findData(periods[0])
            if idx >= 0:
                self.period_combo.setCurrentIndex(idx)
            self._first_load = False
        elif keep is not None:
            idx = self.period_combo.findData(keep)
            if idx >= 0:
                self.period_combo.setCurrentIndex(idx)
        self.period_combo.blockSignals(False)


# --- the page ---------------------------------------------------------------

class RecordsPage(QWidget):
    """Hosts the Imports / Salary / Timesheet tabs."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("Records")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        layout.addWidget(_hint(
            "Browse the raw data the system has stored — every import batch, "
            "every salary row and every timesheet line, period by period."))

        self.tabs = QTabWidget()
        self.imports_tab = ImportsTab()
        self.salary_tab = SalaryTab()
        self.timesheet_tab = TimesheetTab()
        self.tabs.addTab(self.imports_tab, "Import batches")
        self.tabs.addTab(self.salary_tab, "Salary")
        self.tabs.addTab(self.timesheet_tab, "Timesheet")
        self.tabs.currentChanged.connect(self._refresh)
        layout.addWidget(self.tabs, 1)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        # Only load the currently-visible tab — loading all three on every
        # Records nav-click was the main reason the page felt unresponsive
        # when timesheet had thousands of rows.
        self._refresh(self.tabs.currentIndex())

    def _refresh(self, index: int) -> None:
        w = self.tabs.widget(index)
        if hasattr(w, "reload"):
            w.reload()
