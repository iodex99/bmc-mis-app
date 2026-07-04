"""Generate MIS page — pick period(s), set toggles, export the workbook."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
from .. import repository as repo
from ..services import vouchers as vsvc
from ..util import fmt_inr
from ..services.calc import MISOptions, compute
from ..services.report import generate
from ..services.dashboard import generate_dashboard


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
        # Locations (v0.3.98): which locations' employees enter the
        # Employee Register / office-overhead spread. Hidden until the
        # operator adds locations in the masters. All checked by default.
        self.loc_label = QLabel("Locations (Employee Register / overhead):")
        ov.addWidget(self.loc_label)
        self.location_list = QListWidget()
        self.location_list.setSelectionMode(QListWidget.NoSelection)
        self.location_list.setMaximumHeight(110)
        ov.addWidget(self.location_list)
        overhead_note = QLabel(
            "Office overhead: indirect expenses on the Office cost centre "
            "+ office-home staff salaries, divided across the partner-team "
            "employees and the partners, charged to each one's home cost "
            "centre — see the Employee Register sheet in the generated "
            "workbook.")
        overhead_note.setWordWrap(True)
        ov.addWidget(overhead_note)
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
        self._reload_locations()

    def _reload_locations(self) -> None:
        """Populate the location checklist (all checked by default; the
        previous selection survives a reload). Hidden when the operator
        hasn't added any locations in the masters."""
        prev = self._selected_location_ids()
        had_items = self.location_list.count() > 0
        self.location_list.clear()
        try:
            locations = repo.fetch_all("locations", include_inactive=False,
                                       order_by="name")
        except Exception:                                   # pragma: no cover
            locations = []
        for loc in locations:
            item = QListWidgetItem(loc["name"])
            item.setData(Qt.UserRole, loc["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            keep = (loc["id"] in prev) if had_items else True
            item.setCheckState(Qt.Checked if keep else Qt.Unchecked)
            self.location_list.addItem(item)
        visible = bool(locations)
        self.loc_label.setVisible(visible)
        self.location_list.setVisible(visible)

    def _selected_location_ids(self) -> list[int]:
        out = []
        for i in range(self.location_list.count()):
            item = self.location_list.item(i)
            if item.checkState() == Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return out

    def _location_filter_ids(self) -> list[int] | None:
        """The ``MISOptions.location_ids`` value: ``None`` (= no filter)
        when there are no locations or every location is ticked."""
        total = self.location_list.count()
        if total == 0:
            return None
        selected = self._selected_location_ids()
        return None if len(selected) == total else selected

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
            location_ids=self._location_filter_ids())

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
                location_ids=opts.location_ids))

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
                    location_ids=opts.location_ids))
            out = generate(data, path, compare_data)
        except Exception as exc:
            QMessageBox.critical(self, "Generation failed", str(exc))
            return
        # Interactive HTML dashboard alongside the workbook (same computed
        # dataset, so the figures tie out). A dashboard failure must not
        # lose the workbook the operator already has.
        dash_path = Path(out).with_name(Path(out).stem + "_Dashboard.html")
        dash_ok = True
        try:
            generate_dashboard(data, dash_path, compare_data)
        except Exception:                                   # noqa: BLE001
            dash_ok = False
        if dash_ok:
            self.summary.setText(f"Saved:\n{out}\n{dash_path}")
            prompt = (f"Workbook saved to:\n{out}\n\n"
                      f"Interactive dashboard saved to:\n{dash_path}\n\n"
                      "Open them now?")
        else:
            self.summary.setText(f"Saved: {out}\n(Dashboard could not be "
                                 "generated — workbook is unaffected.)")
            prompt = f"Workbook saved to:\n{out}\n\nOpen it now?"
        if QMessageBox.question(self, "MIS generated", prompt) == QMessageBox.Yes:
            try:
                os.startfile(out)  # noqa: S606 (Windows)
                if dash_ok:
                    os.startfile(dash_path)  # opens in the default browser
            except Exception:
                pass


def _pretty(period: str) -> str:
    try:
        d = _dt.date(int(period[:4]), int(period[5:7]), 1)
        return d.strftime("%B %Y")
    except (ValueError, IndexError):
        return period
