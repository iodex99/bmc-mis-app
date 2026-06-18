"""Manual Entry page — add a single voucher / salary / reimbursement row by
hand, for the "just one entry" case where uploading a file is overkill.

Rows land in the same tables the importer writes, so the MIS and dashboard
pick them up automatically. Masters (entity, cost centre, client, …) are
chosen from dropdowns, so manual rows are already resolved — no Review step.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, repository as repo
from ..services import manual_entry as ME
from .master_data import _month_year_combos, _period_from


def _amount_spin() -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(0, 1_000_000_000)
    w.setGroupSeparatorShown(True)
    w.setDecimals(2)
    return w


class _FormBase(QWidget):
    """Shared plumbing: a registry of FK combos refreshed when the page is
    shown (so masters added meanwhile appear), plus a status line."""

    def __init__(self) -> None:
        super().__init__()
        self._fk: list[tuple[QComboBox, str, bool]] = []

    def _fk_combo(self, table: str, allow_none: bool = False) -> QComboBox:
        w = QComboBox()
        self._fk.append((w, table, allow_none))
        self._fill_fk(w, table, allow_none)
        return w

    @staticmethod
    def _fill_fk(w: QComboBox, table: str, allow_none: bool) -> None:
        keep = w.currentData()
        w.clear()
        if allow_none:
            w.addItem("(none)", None)
        for fid, label in repo.fk_options(table):
            w.addItem(label, fid)
        pos = w.findData(keep)
        if pos >= 0:
            w.setCurrentIndex(pos)

    def _name_combo(self, table: str) -> QComboBox:
        """Editable combo of master names (employees) — pick one or type a
        new name (which then surfaces in Review like an uploaded row)."""
        w = QComboBox()
        w.setEditable(True)
        w.addItem("")
        for _fid, label in repo.fk_options(table):
            w.addItem(label)
        w.setCurrentText("")
        return w

    def refresh_masters(self) -> None:
        for w, table, allow_none in self._fk:
            self._fill_fk(w, table, allow_none)


class VoucherForm(_FormBase):
    saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.kind = QComboBox()
        self.kind.addItem("Sales (revenue)", config.VCH_SALES)
        self.kind.addItem("Expense / Purchase", config.VCH_EXPENSE)
        self.kind.currentIndexChanged.connect(self._toggle_kind)
        self.entity = self._fk_combo("entities", allow_none=True)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd-MMM-yyyy")
        self.cost_centre = self._fk_combo("cost_centres")
        self.client = self._fk_combo("clients", allow_none=True)
        self.manager = self._fk_combo("managers", allow_none=True)
        self.service = self._fk_combo("services", allow_none=True)
        self.exp_type = QComboBox()
        self.exp_type.addItem("Professional Fees", "Professional Fees")
        self.exp_type.addItem("Indirect Expense", "Indirect Expense")
        self.amount = _amount_spin()
        self.tax = _amount_spin()
        self.party = QLineEdit()
        self.vch_no = QLineEdit()
        self.vch_no.setPlaceholderText("optional — auto-generated if blank")
        self.desc = QLineEdit()

        form.addRow("Type *:", self.kind)
        form.addRow("Entity:", self.entity)
        form.addRow("Date *:", self.date)
        form.addRow("Cost centre *:", self.cost_centre)
        form.addRow("Amount (net) *:", self.amount)
        form.addRow("Tax (optional):", self.tax)
        self._exp_label = QLabel("Type of expense:")
        form.addRow(self._exp_label, self.exp_type)
        form.addRow("Party name:", self.party)
        form.addRow("Client:", self.client)
        form.addRow("Manager:", self.manager)
        form.addRow("Service:", self.service)
        form.addRow("Voucher no:", self.vch_no)
        form.addRow("Description:", self.desc)
        self._bar(form)
        self._toggle_kind()

    def _bar(self, form) -> None:
        bar = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("pageNote")
        bar.addWidget(self.status)
        bar.addStretch(1)
        btn = QPushButton("＋ Add voucher")
        btn.setObjectName("primary")
        btn.clicked.connect(self._save)
        bar.addWidget(btn)
        form.addRow("", self._wrap(bar))

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _toggle_kind(self) -> None:
        is_exp = self.kind.currentData() == config.VCH_EXPENSE
        self.exp_type.setVisible(is_exp)
        self._exp_label.setVisible(is_exp)

    def _save(self) -> None:
        if self.cost_centre.currentData() is None:
            QMessageBox.warning(self, "Cost centre required",
                                "Pick the cost centre this voucher belongs to.")
            return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Amount required",
                                "Enter a net amount greater than zero.")
            return
        kind = self.kind.currentData()
        ME.add_voucher(
            entity_id=self.entity.currentData(),
            txn_date=self.date.date().toPython(),
            kind=kind,
            cost_centre_id=self.cost_centre.currentData(),
            amount=self.amount.value(),
            tax_amount=self.tax.value(),
            vch_no=self.vch_no.text().strip(),
            party_name=self.party.text().strip(),
            client_id=self.client.currentData(),
            manager_id=self.manager.currentData(),
            service_id=self.service.currentData(),
            expense_type=(self.exp_type.currentData()
                          if kind == config.VCH_EXPENSE else None),
            description=self.desc.text().strip())
        self.status.setText("✓ Voucher added.")
        self.amount.setValue(0)
        self.tax.setValue(0)
        self.party.clear()
        self.vch_no.clear()
        self.desc.clear()
        self.saved.emit()


class SalaryForm(_FormBase):
    saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.month, self.year = _month_year_combos()
        self.employee = self._name_combo("employees")
        self.cost_centre = self._fk_combo("cost_centres")
        self.entity = self._fk_combo("entities", allow_none=True)
        self.category = QComboBox()
        self.category.addItems(["", "Employee", "CA Article", "CMA Article"])
        self.salary = _amount_spin()
        self.reimb = _amount_spin()

        form.addRow("Month *:", self.month)
        form.addRow("Year *:", self.year)
        form.addRow("Employee *:", self.employee)
        form.addRow("Cost centre *:", self.cost_centre)
        form.addRow("Entity:", self.entity)
        form.addRow("Category:", self.category)
        form.addRow("Salary paid *:", self.salary)
        form.addRow("Reimbursement (optional):", self.reimb)
        bar = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("pageNote")
        bar.addWidget(self.status)
        bar.addStretch(1)
        btn = QPushButton("＋ Add salary row")
        btn.setObjectName("primary")
        btn.clicked.connect(self._save)
        bar.addWidget(btn)
        w = QWidget()
        w.setLayout(bar)
        form.addRow("", w)

    def _save(self) -> None:
        name = self.employee.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Employee required",
                                "Enter or pick the employee name.")
            return
        if self.cost_centre.currentData() is None:
            QMessageBox.warning(self, "Cost centre required",
                                "Pick the employee's cost centre.")
            return
        if self.salary.value() <= 0:
            QMessageBox.warning(self, "Salary required",
                                "Enter a salary amount greater than zero.")
            return
        ME.add_salary(
            period=_period_from(self.month, self.year),
            employee_name=name,
            cost_centre_id=self.cost_centre.currentData(),
            entity_id=self.entity.currentData(),
            category=self.category.currentText(),
            salary_paid=self.salary.value(),
            reimbursement=self.reimb.value())
        self.status.setText("✓ Salary row added.")
        self.salary.setValue(0)
        self.reimb.setValue(0)
        self.saved.emit()


class ReimbursementForm(_FormBase):
    saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.month, self.year = _month_year_combos()
        self.employee = self._name_combo("employees")
        self.client = self._fk_combo("clients", allow_none=True)
        self.amount = _amount_spin()
        self.reimbursable = QCheckBox("Client reimbursable (recovered from "
                                      "the client)")

        form.addRow("Month *:", self.month)
        form.addRow("Year *:", self.year)
        form.addRow("Employee *:", self.employee)
        form.addRow("Client:", self.client)
        form.addRow("Amount *:", self.amount)
        form.addRow("", self.reimbursable)
        bar = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("pageNote")
        bar.addWidget(self.status)
        bar.addStretch(1)
        btn = QPushButton("＋ Add reimbursement")
        btn.setObjectName("primary")
        btn.clicked.connect(self._save)
        bar.addWidget(btn)
        w = QWidget()
        w.setLayout(bar)
        form.addRow("", w)

    def _save(self) -> None:
        name = self.employee.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Employee required",
                                "Enter or pick the employee name.")
            return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Amount required",
                                "Enter an amount greater than zero.")
            return
        ME.add_reimbursement(
            period=_period_from(self.month, self.year),
            employee_name=name,
            amount=self.amount.value(),
            client_id=self.client.currentData(),
            client_reimbursable=self.reimbursable.isChecked())
        self.status.setText("✓ Reimbursement added.")
        self.amount.setValue(0)
        self.reimbursable.setChecked(False)
        self.saved.emit()


class ManualEntryPage(QWidget):
    """Hosts the voucher / salary / reimbursement entry forms."""

    saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel("Manual Entry")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        note = QLabel(
            "Add a single voucher, salary or reimbursement row by hand — for "
            "the one-off entry where uploading a file is overkill. Entries go "
            "straight into the MIS. Fields marked * are required.")
        note.setObjectName("pageNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.tabs = QTabWidget()
        self.voucher = VoucherForm()
        self.salary = SalaryForm()
        self.reimb = ReimbursementForm()
        self.tabs.addTab(self.voucher, "Voucher")
        self.tabs.addTab(self.salary, "Salary")
        self.tabs.addTab(self.reimb, "Reimbursement")
        for f in (self.voucher, self.salary, self.reimb):
            f.saved.connect(self.saved)
        layout.addWidget(self.tabs, 1)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        for f in (self.voucher, self.salary, self.reimb):
            f.refresh_masters()
