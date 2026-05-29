"""Dashboard page — at-a-glance status and what needs attention."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..database import transaction
from ..services import resolution, vouchers as vsvc
from ..util import fmt_inr


def _counts() -> dict:
    with transaction() as conn:
        def n(sql):
            return conn.execute(sql).fetchone()[0]
        return {
            "entities": n("SELECT COUNT(*) FROM entities WHERE active=1"),
            "cost_centres": n("SELECT COUNT(*) FROM cost_centres WHERE active=1"),
            "managers": n("SELECT COUNT(*) FROM managers WHERE active=1"),
            "employees": n("SELECT COUNT(*) FROM employees WHERE active=1"),
            "clients": n("SELECT COUNT(*) FROM clients WHERE active=1"),
            "vouchers": n("SELECT COUNT(*) FROM vouchers"),
            "timesheet": n("SELECT COUNT(*) FROM timesheet_entries"),
            "salary": n("SELECT COUNT(*) FROM salary_entries"),
            "batches": n("SELECT COUNT(*) FROM import_batches"),
        }


class MetricCard(QGroupBox):
    """A modern metric tile: title, large value, supporting detail."""

    def __init__(self, title: str) -> None:
        super().__init__(title.upper())
        self.setObjectName("metricCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(4)
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        self.detail = QLabel("")
        self.detail.setObjectName("metricDetail")
        self.detail.setWordWrap(True)
        lay.addWidget(self.value)
        lay.addWidget(self.detail)
        lay.addStretch(1)

    def set(self, value, detail: str = "") -> None:
        self.value.setText(str(value))
        self.detail.setText(detail)


class DashboardPage(QWidget):
    """Shows headline counts, pending review items and next-step guidance."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        heading = QLabel("Dashboard")
        heading.setObjectName("pageHeading")
        root.addWidget(heading)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("pageNote")
        root.addWidget(self.subtitle)
        # Tiny visible marker so an installed user can confirm the auto-update
        # actually landed.
        tagline = QLabel("Board-ready MIS — compiled from your Tally, "
                         "timesheet and salary data.")
        tagline.setObjectName("pageNote")
        root.addWidget(tagline)

        grid = QGridLayout()
        grid.setSpacing(14)
        root.addLayout(grid)
        self.cards = {
            "data": MetricCard("Imported data"),
            "periods": MetricCard("Periods on record"),
            "masters": MetricCard("Client master"),
            "review": MetricCard("Pending review"),
        }
        for i, key in enumerate(("data", "periods", "masters", "review")):
            grid.addWidget(self.cards[key], 0, i)
            grid.setColumnStretch(i, 1)

        self.todo = QLabel("")
        self.todo.setObjectName("nextStepsCard")
        self.todo.setWordWrap(True)
        self.todo.setTextFormat(Qt.RichText)
        root.addWidget(self.todo)
        root.addStretch(1)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        c = _counts()
        periods = vsvc.list_periods()
        unresolved_c = len(resolution.unresolved_clients())
        unresolved_e = len(resolution.unresolved_employees())
        unassigned = vsvc.split_stats()["vouchers_unassigned"]

        self.subtitle.setText(
            f"{c['batches']} import batch(es) · "
            f"{len(periods)} period(s) on record")
        self.cards["data"].set(
            fmt_inr(c['vouchers'] + c['timesheet'] + c['salary']),
            f"{fmt_inr(c['vouchers'])} vouchers · "
            f"{fmt_inr(c['timesheet'])} timesheet rows · "
            f"{fmt_inr(c['salary'])} salary rows")
        self.cards["periods"].set(
            len(periods),
            ", ".join(periods[:6]) + (" …" if len(periods) > 6 else "")
            if periods else "No data imported yet.")
        self.cards["masters"].set(
            fmt_inr(c['clients']),
            f"{c['entities']} entities · {c['cost_centres']} cost centres · "
            f"{c['managers']} managers · {c['employees']} employees")
        self.cards["review"].set(
            fmt_inr(unresolved_c + unresolved_e + unassigned),
            f"{fmt_inr(unresolved_c)} unmapped clients · "
            f"{fmt_inr(unresolved_e)} unmapped employees · "
            f"{fmt_inr(unassigned)} vouchers with unassigned splits")

        steps = []
        if c["batches"] == 0:
            steps.append("Start on the <b>Import Files</b> page — upload a "
                          "Tally register, the timesheet or the salary sheet.")
        if unresolved_c or unresolved_e:
            steps.append("Go to <b>Review &amp; Map</b> to resolve unmapped "
                          "clients and employees.")
        if unassigned:
            steps.append(f"{unassigned} voucher(s) still have an unassigned "
                          "cost centre — fix them under <b>Review &amp; Map "
                          "→ Vouchers</b>.")
        if c["batches"] and not steps:
            steps.append("All set — head to <b>Generate MIS</b> to export the "
                          "board-ready workbook.")
        self.todo.setText(
            "<div style='font-weight:600;margin-bottom:6px;'>Next steps</div>"
            "• " + "<br>• ".join(steps))
