"""Generate MIS page — pick period(s), set toggles, export the workbook."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..services import vouchers as vsvc
from ..util import fmt_inr
from ..services.calc import (
    MISOptions,
    OVERHEAD_EQUAL,
    OVERHEAD_REVENUE,
    OVERHEAD_SEPARATE,
    compute,
)
from ..services.report import generate

_OVERHEAD_CHOICES = [
    ("Show Office separately (no allocation)", OVERHEAD_SEPARATE),
    ("Allocate Office to partners by revenue share", OVERHEAD_REVENUE),
    ("Allocate Office to partners equally", OVERHEAD_EQUAL),
]


class GeneratePage(QWidget):
    """Operator chooses periods + toggles and exports the formula-driven MIS."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        heading = QLabel("Generate MIS")
        heading.setObjectName("pageHeading")
        root.addWidget(heading)
        note = QLabel("Select one or more months, set the options and export "
                      "the board-ready Excel workbook.")
        note.setObjectName("pageNote")
        root.addWidget(note)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        # --- period selection ----------------------------------------------
        period_box = QGroupBox("Reporting period(s)")
        pv = QVBoxLayout(period_box)
        self.period_list = QListWidget()
        self.period_list.setSelectionMode(QListWidget.NoSelection)
        pv.addWidget(self.period_list)
        sel_bar = QHBoxLayout()
        all_btn = QPushButton("Select all")
        none_btn = QPushButton("Clear")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        sel_bar.addWidget(all_btn)
        sel_bar.addWidget(none_btn)
        sel_bar.addStretch(1)
        pv.addLayout(sel_bar)
        body.addWidget(period_box, 1)

        # --- comparison period (optional) ----------------------------------
        cmp_box = QGroupBox("Compare with (optional)")
        cv = QVBoxLayout(cmp_box)
        cv.addWidget(QLabel("Tick months to show as a comparison column."))
        self.compare_list = QListWidget()
        self.compare_list.setSelectionMode(QListWidget.NoSelection)
        cv.addWidget(self.compare_list)
        clear_cmp = QPushButton("Clear comparison")
        clear_cmp.clicked.connect(self._clear_compare)
        cv.addWidget(clear_cmp)
        body.addWidget(cmp_box, 1)

        # --- options --------------------------------------------------------
        opt_box = QGroupBox("Options")
        ov = QVBoxLayout(opt_box)
        self.reimb_check = QCheckBox("Include reimbursements in the MIS")
        self.reimb_check.setChecked(True)
        ov.addWidget(self.reimb_check)
        ov.addWidget(QLabel("Office / shared expenses:"))
        self.overhead_combo = QComboBox()
        for label, key in _OVERHEAD_CHOICES:
            self.overhead_combo.addItem(label, key)
        ov.addWidget(self.overhead_combo)
        ov.addStretch(1)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        ov.addWidget(self.summary)
        body.addWidget(opt_box, 1)

        # --- actions --------------------------------------------------------
        bar = QHBoxLayout()
        preview_btn = QPushButton("Preview totals")
        self.generate_btn = QPushButton("Generate MIS workbook…")
        self.generate_btn.setObjectName("primary")
        preview_btn.clicked.connect(self._preview)
        self.generate_btn.clicked.connect(self._generate)
        bar.addStretch(1)
        bar.addWidget(preview_btn)
        bar.addWidget(self.generate_btn)
        root.addLayout(bar)

    # -- lifecycle -----------------------------------------------------------
    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._reload_periods()

    def _reload_periods(self) -> None:
        checked = self._selected_periods()
        compare = self._compare_periods()
        periods = vsvc.list_periods()
        self.period_list.clear()
        self.compare_list.clear()
        for p in periods:
            item = QListWidgetItem(_pretty(p))
            item.setData(Qt.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if (p in checked or not checked)
                               else Qt.Unchecked)
            self.period_list.addItem(item)

            citem = QListWidgetItem(_pretty(p))
            citem.setData(Qt.UserRole, p)
            citem.setFlags(citem.flags() | Qt.ItemIsUserCheckable)
            citem.setCheckState(Qt.Checked if p in compare else Qt.Unchecked)
            self.compare_list.addItem(citem)

    def _set_all(self, state: bool) -> None:
        for i in range(self.period_list.count()):
            self.period_list.item(i).setCheckState(
                Qt.Checked if state else Qt.Unchecked)

    def _clear_compare(self) -> None:
        for i in range(self.compare_list.count()):
            self.compare_list.item(i).setCheckState(Qt.Unchecked)

    def _checked(self, widget) -> list[str]:
        out = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return sorted(out)

    def _selected_periods(self) -> list[str]:
        return self._checked(self.period_list)

    def _compare_periods(self) -> list[str]:
        return self._checked(self.compare_list)

    def _options(self) -> MISOptions | None:
        periods = self._selected_periods()
        if not periods:
            QMessageBox.warning(self, "No period",
                                "Select at least one reporting month.")
            return None
        return MISOptions(
            periods=periods,
            include_reimbursement=self.reimb_check.isChecked(),
            overhead_mode=self.overhead_combo.currentData())

    # -- actions -------------------------------------------------------------
    def _preview(self) -> None:
        opts = self._options()
        if not opts:
            return
        data = compute(opts)
        compare_periods = self._compare_periods()
        compare_data = None
        if compare_periods:
            compare_data = compute(MISOptions(
                periods=compare_periods,
                include_reimbursement=opts.include_reimbursement,
                overhead_mode=opts.overhead_mode))

        def block(label: str, periods: list[str], d) -> str:
            n_rev = len(d.revenue_facts)
            n_exp = len(d.expense_facts)
            n_lab = len(d.labour_facts)
            return (
                f"<div style='margin-bottom:10px;'>"
                f"<b>{label}: {', '.join(periods)}</b><br>"
                f"&nbsp;&nbsp;Revenue: ₹ {fmt_inr(d.total_revenue)} "
                f"({fmt_inr(n_rev)} entr{'ies' if n_rev != 1 else 'y'})<br>"
                f"&nbsp;&nbsp;Cost: ₹ {fmt_inr(d.total_cost)} "
                f"({fmt_inr(n_exp)} expense, {fmt_inr(n_lab)} labour)<br>"
                f"&nbsp;&nbsp;Net profit: ₹ {fmt_inr(d.total_profit)}<br>"
                f"&nbsp;&nbsp;Cost centres with activity: "
                f"{len(d.cost_centres)}"
                f"</div>")

        text = "<b>Preview</b><br><br>" + block("Primary", opts.periods, data)
        if compare_data:
            text += block("Comparison", compare_periods, compare_data)
        self.summary.setText(text)

    def _generate(self) -> None:
        opts = self._options()
        if not opts:
            return
        default = config.EXPORT_DIR / (
            f"MIS_{'_'.join(opts.periods)}_"
            f"{_dt.datetime.now():%Y%m%d_%H%M}.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MIS workbook", str(default), "Excel files (*.xlsx)")
        if not path:
            return
        compare_periods = self._compare_periods()
        try:
            data = compute(opts)
            compare_data = None
            if compare_periods:
                compare_data = compute(MISOptions(
                    periods=compare_periods,
                    include_reimbursement=opts.include_reimbursement,
                    overhead_mode=opts.overhead_mode))
            out = generate(data, path, compare_data)
        except Exception as exc:
            QMessageBox.critical(self, "Generation failed", str(exc))
            return
        self.summary.setText(f"Saved: {out}")
        if QMessageBox.question(
                self, "MIS generated",
                f"Workbook saved to:\n{out}\n\nOpen it now?") == QMessageBox.Yes:
            try:
                os.startfile(out)  # noqa: S606 (Windows)
            except Exception:
                pass


def _pretty(period: str) -> str:
    try:
        d = _dt.date(int(period[:4]), int(period[5:7]), 1)
        return d.strftime("%B %Y")
    except (ValueError, IndexError):
        return period
