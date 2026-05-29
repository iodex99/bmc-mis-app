"""Dashboard page — welcome state + at-a-glance status + quick actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..database import transaction
from ..services import resolution, vouchers as vsvc
from ..util import fmt_inr


# Each nav entry the dashboard can jump to: (label, index_in_NAV_ITEMS).
# Indices match app/ui/main_window.NAV_ITEMS exactly.
NAV_IMPORT = 1
NAV_REVIEW = 2
NAV_MASTER = 3
NAV_GENERATE = 4


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


def _money_totals() -> dict:
    with transaction() as conn:
        def f(sql):
            return float(conn.execute(sql).fetchone()[0] or 0)
        return {
            "revenue": f(
                "SELECT SUM(s.amount) FROM voucher_splits s "
                "JOIN vouchers v ON v.id = s.voucher_id "
                "WHERE v.kind = 'sales'"),
            "expense": f(
                "SELECT SUM(s.amount) FROM voucher_splits s "
                "JOIN vouchers v ON v.id = s.voucher_id "
                "WHERE v.kind = 'expense'"),
            "salary": f("SELECT SUM(salary_paid) FROM salary_entries"),
        }


# --- visual building blocks --------------------------------------------------

class MetricCard(QFrame):
    """A single KPI tile."""

    def __init__(self, title: str, *, accent: str = "indigo") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", accent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(4)

        head = QLabel(title.upper())
        head.setObjectName("cardLabel")
        lay.addWidget(head)

        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        lay.addWidget(self.value)

        self.detail = QLabel("")
        self.detail.setObjectName("metricDetail")
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)
        lay.addStretch(1)

    def set(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


class QuickActionCard(QFrame):
    """A clickable card that triggers navigating elsewhere in the app."""

    clicked = Signal(int)

    def __init__(self, icon: str, title: str, subtitle: str,
                 nav_index: int) -> None:
        super().__init__()
        self.setObjectName("quickCard")
        self._nav = nav_index
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        icon_label = QLabel(icon)
        icon_label.setObjectName("quickIcon")
        title_label = QLabel(title)
        title_label.setObjectName("quickTitle")
        head.addWidget(icon_label)
        head.addWidget(title_label)
        head.addStretch(1)
        arrow = QLabel("→")
        arrow.setObjectName("quickArrow")
        head.addWidget(arrow)
        lay.addLayout(head)

        sub = QLabel(subtitle)
        sub.setObjectName("quickSubtitle")
        sub.setWordWrap(True)
        lay.addWidget(sub)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._nav)
        super().mouseReleaseEvent(event)


# --- the page ---------------------------------------------------------------

class DashboardPage(QWidget):
    """Headline numbers + quick actions tuned to the current state of the data."""

    navigate = Signal(int)     # emit a NAV_ITEMS index to jump to that page

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

        # Welcome (no-data) and body (data) are stacked so only one ever
        # takes layout space — keeps the dashboard top-aligned in both states.
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        welcome_holder = QWidget()
        welcome_lay = QVBoxLayout(welcome_holder)
        welcome_lay.setContentsMargins(0, 0, 0, 0)
        welcome_lay.setSpacing(0)
        self.welcome = self._build_welcome()
        welcome_lay.addWidget(self.welcome)
        welcome_lay.addStretch(1)
        self.stack.addWidget(welcome_holder)

        self.body = QWidget()
        body_lay = QVBoxLayout(self.body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(14)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        body_lay.addLayout(metrics)
        self.revenue_card = MetricCard("Total revenue", accent="indigo")
        self.expense_card = MetricCard("Total costs", accent="rose")
        self.profit_card = MetricCard("Net of revenue − costs", accent="emerald")
        self.review_card = MetricCard("Items to review", accent="amber")
        for i, c in enumerate((
                self.revenue_card, self.expense_card,
                self.profit_card, self.review_card)):
            metrics.addWidget(c, 0, i)
            metrics.setColumnStretch(i, 1)

        body_lay.addWidget(_section_title("Next steps"))
        actions = QGridLayout()
        actions.setSpacing(12)
        body_lay.addLayout(actions)
        self.act_review = QuickActionCard(
            "🧩", "Resolve pending items",
            "Map unknown clients / employees / cost-centre strings.",
            NAV_REVIEW)
        self.act_import = QuickActionCard(
            "📥", "Import more files",
            "Add Tally registers, timesheet or salary for another period.",
            NAV_IMPORT)
        self.act_master = QuickActionCard(
            "🏷", "Master data",
            "Edit entities, partners, managers, clients, services, targets.",
            NAV_MASTER)
        self.act_generate = QuickActionCard(
            "📊", "Generate MIS workbook",
            "Pick a period, set the toggles and export the board-ready file.",
            NAV_GENERATE)
        for i, c in enumerate((self.act_review, self.act_import,
                               self.act_master, self.act_generate)):
            actions.addWidget(c, i // 2, i % 2)
            actions.setRowStretch(i // 2, 1)
            actions.setColumnStretch(i % 2, 1)
            c.clicked.connect(self.navigate.emit)

        body_lay.addStretch(1)
        self.stack.addWidget(self.body)

    # -- welcome state -------------------------------------------------------
    def _build_welcome(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("welcomePanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(28, 26, 28, 26)
        lay.setSpacing(8)

        title = QLabel("Welcome to the MIS Generator 👋")
        title.setObjectName("welcomeTitle")
        lay.addWidget(title)

        sub = QLabel(
            "Nothing imported yet. Get the system going in three quick steps:"
            "<ul style='margin-top:6px;'>"
            "<li>Import the Tally <b>Sales</b> and <b>Purchase</b> registers, "
            "the <b>Timesheet</b> and the <b>Salary</b> sheet.</li>"
            "<li>On the <b>Review & Map</b> page, match any unknown client "
            "or cost-centre strings to your masters.</li>"
            "<li>On <b>Generate MIS</b>, pick a period and export the "
            "workbook.</li></ul>")
        sub.setObjectName("welcomeBody")
        sub.setWordWrap(True)
        sub.setTextFormat(Qt.RichText)
        lay.addWidget(sub)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        go_import = QPushButton("📥 Start by importing files")
        go_import.setObjectName("primary")
        go_import.clicked.connect(lambda: self.navigate.emit(NAV_IMPORT))
        go_master = QPushButton("Open master data first")
        go_master.clicked.connect(lambda: self.navigate.emit(NAV_MASTER))
        bar.addWidget(go_import)
        bar.addWidget(go_master)
        bar.addStretch(1)
        lay.addLayout(bar)

        return panel

    # -- lifecycle -----------------------------------------------------------
    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        c = _counts()
        money = _money_totals()
        periods = vsvc.list_periods()
        ucl = len(resolution.unresolved_clients())
        uem = len(resolution.unresolved_employees())
        ucc = len(resolution.unresolved_cc_strings())
        vouchers_unassigned = vsvc.split_stats()["vouchers_unassigned"]

        has_data = c["batches"] > 0
        self.stack.setCurrentIndex(1 if has_data else 0)
        if not has_data:
            self.subtitle.setText("Let's get the first month of data in.")
            return

        period_summary = (
            f"{len(periods)} period" + ("s" if len(periods) != 1 else "")
            + " on record"
            + (f"  ·  latest {periods[0]}" if periods else ""))
        self.subtitle.setText(
            f"{c['batches']} import batch{'es' if c['batches'] != 1 else ''}"
            f"  ·  {period_summary}")

        revenue = money["revenue"]
        expense = money["expense"]
        salary = money["salary"]
        profit = revenue - expense - salary

        self.revenue_card.set(
            f"₹ {fmt_inr(revenue, 0)}",
            f"From {fmt_inr(c['vouchers'])} voucher{'s' if c['vouchers'] != 1 else ''}, "
            f"{fmt_inr(c['clients'])} client{'s' if c['clients'] != 1 else ''} on master.")
        self.expense_card.set(
            f"₹ {fmt_inr(expense + salary, 0)}",
            f"Direct ₹ {fmt_inr(expense)}  ·  Salary ₹ {fmt_inr(salary)}.")
        self.profit_card.set(
            f"₹ {fmt_inr(profit, 0)}",
            f"Across {c['cost_centres']} cost centres, "
            f"{c['managers']} managers, {c['employees']} employees.")

        review_total = ucl + uem + ucc + vouchers_unassigned
        if review_total:
            details = []
            if ucl:
                details.append(f"{fmt_inr(ucl)} client{'s' if ucl != 1 else ''}")
            if uem:
                details.append(f"{fmt_inr(uem)} employee{'s' if uem != 1 else ''}")
            if ucc:
                details.append(f"{fmt_inr(ucc)} cost-centre string{'s' if ucc != 1 else ''}")
            if vouchers_unassigned:
                details.append(
                    f"{fmt_inr(vouchers_unassigned)} voucher{'s' if vouchers_unassigned != 1 else ''}")
            self.review_card.set(fmt_inr(review_total), " · ".join(details))
        else:
            self.review_card.set("0", "Everything's mapped — ready to generate.")


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label
