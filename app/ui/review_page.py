"""Review & Map page — resolve unknown clients/employees and edit splits."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
    debounced,
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
            "your master list yet. Click <b>Resolve →</b> on a row to map it, "
            "or <b>Delete</b> to permanently remove the underlying rows. "
            "Use Ctrl+click / Shift+click to multi-select.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        self.bulk_delete_btn = QPushButton("🗑 Delete selected")
        self.bulk_delete_btn.setObjectName("danger")
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        auto_btn = QPushButton("⚡ Auto-resolve known")
        bulk_btn = QPushButton("➕ Create all as new")
        auto_btn.clicked.connect(self._auto)
        bulk_btn.clicked.connect(self._bulk)
        bar.addWidget(self.bulk_delete_btn)
        bar.addWidget(auto_btn)
        bar.addWidget(bulk_btn)
        layout.addLayout(bar)

        # Search row.
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name…")
        self._sched_reload, self._search_timer = debounced(self.reload)
        self.search.textChanged.connect(self._sched_reload)
        search_bar.addWidget(self.search)
        layout.addLayout(search_bar)

        self.table = QTableWidget()
        setup_data_table(self.table, multi_select=True)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        self.table.itemSelectionChanged.connect(self._update_bulk_button)
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
        all_rows = resolution.unresolved_clients()
        q = self.search.text().strip().lower()
        if q:
            self._rows = [r for r in all_rows if q in r["raw"].lower()]
        else:
            self._rows = all_rows
        n = len(self._rows)
        total = len(all_rows)
        if total == 0:
            self.info.setText("All clients mapped")
        elif n == total:
            self.info.setText(f"{n} client name{'s' if n != 1 else ''} need mapping")
        else:
            self.info.setText(
                f"{n} of {total} match{'es' if n != 1 else ''} your search")
        self.empty.setVisible(total == 0)
        self.table.setVisible(n > 0 or total > 0)
        if n:
            rows = [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
                    for r in self._rows]
            fill_table_with_actions(
                self.table,
                ["Raw client name", "Seen in", "Rows"],
                rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                secondary_label="Delete",
                secondary_callback=self._delete_row,
                secondary_object_name="rowActionDanger",
                status_for_row=_warn_pill,
                stretch_col=0,
            )
        else:
            # search returned nothing
            fill_table_with_actions(
                self.table, ["Raw client name", "Seen in", "Rows"], [],
                stretch_col=0)
        self._update_bulk_button()

    def _update_bulk_button(self) -> None:
        sel = len({i.row() for i in self.table.selectedIndexes()})
        self.bulk_delete_btn.setEnabled(sel > 0)
        self.bulk_delete_btn.setText(
            f"🗑 Delete selected ({sel})" if sel else "🗑 Delete selected")

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
                "names?\n\nWhere the Sales Register's Cost Center column has a "
                "saved partner mapping, the cost centre is filled in "
                "automatically; otherwise it's left blank for you to set "
                "later in Master Data.") != QMessageBox.Yes:
            return
        n = resolution.bulk_create_clients()
        QMessageBox.information(
            self, "Done",
            f"{n} client(s) created. Open the Master Data → Clients tab to "
            "review which ones got a cost centre auto-assigned.")
        self.reload()

    def _resolve_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        raw = self._rows[idx]["raw"]
        dlg = ResolveClientDialog(raw, self)
        if dlg.exec() == ResolveClientDialog.Accepted:
            dlg.apply()
            self.reload()

    def _delete_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        r = self._rows[idx]
        n_rows = r["count"]
        if QMessageBox.warning(
                self, "Delete this name?",
                f"This permanently deletes all <b>{n_rows} source row(s)</b> "
                f"for <b>{r['raw']}</b> (sales vouchers and / or timesheet "
                "lines).<br><br>The MIS will no longer include any data for "
                "this name. This cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        resolution.delete_unmapped_client_rows(r["raw"])
        self.reload()

    def _bulk_delete(self) -> None:
        indices = sorted({i.row() for i in self.table.selectedIndexes()})
        if not indices:
            return
        raws = [self._rows[i]["raw"] for i in indices]
        total_rows = sum(self._rows[i]["count"] for i in indices)
        if QMessageBox.warning(
                self, f"Delete {len(raws)} names?",
                f"Permanently delete <b>{len(raws)} client name(s)</b> and "
                f"all <b>{total_rows} underlying row(s)</b>?<br><br>"
                "This cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        for raw in raws:
            resolution.delete_unmapped_client_rows(raw)
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
            "have a master record. <b>Resolve →</b> maps them; <b>Delete</b> "
            "removes their timesheet / salary rows entirely. Ctrl+click / "
            "Shift+click to multi-select.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        self.bulk_delete_btn = QPushButton("🗑 Delete selected")
        self.bulk_delete_btn.setObjectName("danger")
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        bulk_btn = QPushButton("➕ Create all as new")
        bulk_btn.clicked.connect(self._bulk)
        bar.addWidget(self.bulk_delete_btn)
        bar.addWidget(bulk_btn)
        layout.addLayout(bar)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name…")
        self._sched_reload, self._search_timer = debounced(self.reload)
        self.search.textChanged.connect(self._sched_reload)
        search_bar.addWidget(self.search)
        layout.addLayout(search_bar)

        self.table = QTableWidget()
        setup_data_table(self.table, multi_select=True)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        self.table.itemSelectionChanged.connect(self._update_bulk_button)
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
        all_rows = resolution.unresolved_employees()
        q = self.search.text().strip().lower()
        if q:
            self._rows = [r for r in all_rows if q in r["raw"].lower()]
        else:
            self._rows = all_rows
        n = len(self._rows)
        total = len(all_rows)
        if total == 0:
            self.info.setText("All employees mapped")
        elif n == total:
            self.info.setText(f"{n} employee name{'s' if n != 1 else ''} need mapping")
        else:
            self.info.setText(
                f"{n} of {total} match{'es' if n != 1 else ''} your search")
        self.empty.setVisible(total == 0)
        self.table.setVisible(n > 0 or total > 0)
        if n:
            rows = [[r["raw"], ", ".join(sorted(r["sources"])), r["count"]]
                    for r in self._rows]
            fill_table_with_actions(
                self.table,
                ["Raw employee name", "Seen in", "Rows"],
                rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                secondary_label="Delete",
                secondary_callback=self._delete_row,
                secondary_object_name="rowActionDanger",
                status_for_row=_warn_pill,
                stretch_col=0,
            )
        else:
            fill_table_with_actions(
                self.table, ["Raw employee name", "Seen in", "Rows"], [],
                stretch_col=0)
        self._update_bulk_button()

    def _update_bulk_button(self) -> None:
        sel = len({i.row() for i in self.table.selectedIndexes()})
        self.bulk_delete_btn.setEnabled(sel > 0)
        self.bulk_delete_btn.setText(
            f"🗑 Delete selected ({sel})" if sel else "🗑 Delete selected")

    def _bulk(self) -> None:
        if not self._rows:
            return
        if QMessageBox.question(
                self, "Create all as new employees",
                f"Create {len(self._rows)} new employee record(s)?\n\n"
                "Manager and cost centre are auto-inferred where the system "
                "can, otherwise left blank.") != QMessageBox.Yes:
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

    def _delete_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        r = self._rows[idx]
        n_rows = r["count"]
        if QMessageBox.warning(
                self, "Delete this name?",
                f"This permanently deletes all <b>{n_rows} timesheet / "
                f"salary row(s)</b> for <b>{r['raw']}</b>.<br><br>"
                "The MIS will no longer include this person's hours or "
                "salary. This cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        resolution.delete_unmapped_employee_rows(r["raw"])
        self.reload()

    def _bulk_delete(self) -> None:
        indices = sorted({i.row() for i in self.table.selectedIndexes()})
        if not indices:
            return
        raws = [self._rows[i]["raw"] for i in indices]
        total_rows = sum(self._rows[i]["count"] for i in indices)
        if QMessageBox.warning(
                self, f"Delete {len(raws)} names?",
                f"Permanently delete <b>{len(raws)} employee name(s)</b> "
                f"and all <b>{total_rows} underlying row(s)</b>?<br><br>"
                "This cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        for raw in raws:
            resolution.delete_unmapped_employee_rows(raw)
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
            "behind each invoice. <b>Resolve →</b> maps it; <b>Delete</b> "
            "drops all invoices that used this string. Ctrl+click / "
            "Shift+click to multi-select.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.info = QLabel()
        self.info.setObjectName("sectionTitle")
        bar.addWidget(self.info)
        bar.addStretch(1)
        self.bulk_delete_btn = QPushButton("🗑 Delete selected")
        self.bulk_delete_btn.setObjectName("danger")
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        auto_btn = QPushButton("⚡ Auto-match all")
        auto_btn.setObjectName("primary")
        auto_btn.clicked.connect(self._auto)
        bar.addWidget(self.bulk_delete_btn)
        bar.addWidget(auto_btn)
        layout.addLayout(bar)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by Cost Centre string…")
        self._sched_reload, self._search_timer = debounced(self.reload)
        self.search.textChanged.connect(self._sched_reload)
        search_bar.addWidget(self.search)
        layout.addLayout(search_bar)

        self.table = QTableWidget()
        setup_data_table(self.table, multi_select=True)
        self.table.doubleClicked.connect(
            lambda idx: self._resolve_row(idx.row()))
        self.table.itemSelectionChanged.connect(self._update_bulk_button)
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
        all_rows = resolution.unresolved_cc_strings()
        q = self.search.text().strip().lower()
        if q:
            self._rows = [r for r in all_rows if q in r["raw"].lower()]
        else:
            self._rows = all_rows
        n = len(self._rows)
        total = len(all_rows)
        if total == 0:
            self.info.setText("All Cost Centre strings mapped")
        elif n == total:
            self.info.setText(
                f"{n} Cost Centre string{'s' if n != 1 else ''} need mapping")
        else:
            self.info.setText(
                f"{n} of {total} match{'es' if n != 1 else ''} your search")
        self.empty.setVisible(total == 0)
        self.table.setVisible(n > 0 or total > 0)
        if n:
            rows = [[r["raw"], r["count"]] for r in self._rows]
            fill_table_with_actions(
                self.table, ["Cost Centre string", "Invoices"], rows,
                action_label="Resolve →",
                action_callback=self._resolve_row,
                secondary_label="Delete",
                secondary_callback=self._delete_row,
                secondary_object_name="rowActionDanger",
                status_for_row=_warn_pill,
                stretch_col=0,
            )
        else:
            fill_table_with_actions(
                self.table, ["Cost Centre string", "Invoices"], [],
                stretch_col=0)
        self._update_bulk_button()

    def _update_bulk_button(self) -> None:
        sel = len({i.row() for i in self.table.selectedIndexes()})
        self.bulk_delete_btn.setEnabled(sel > 0)
        self.bulk_delete_btn.setText(
            f"🗑 Delete selected ({sel})" if sel else "🗑 Delete selected")

    def _auto(self) -> None:
        # Two passes: first re-apply saved mappings, then smart fuzzy-match
        # any new strings against partners / managers. Most rows resolve
        # themselves on first import — this button is for re-running after
        # adding a new partner or manager to the masters.
        applied = resolution.apply_known_cc_string_mappings()
        matched = resolution.auto_match_cc_strings()
        msg = []
        if matched:
            msg.append(f"{matched} string(s) auto-matched to a partner.")
        if applied:
            msg.append(f"{applied} voucher split(s) updated from saved mappings.")
        if not msg:
            msg.append("Nothing new to auto-match. Resolve remaining rows "
                       "manually.")
        QMessageBox.information(self, "Auto-match", "\n".join(msg))
        self.reload()

    def _resolve_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        raw = self._rows[idx]["raw"]
        dlg = ResolveCcStringDialog(raw, self)
        if dlg.exec() == ResolveCcStringDialog.Accepted:
            dlg.apply()
            self.reload()

    def _delete_row(self, idx: int) -> None:
        if not (0 <= idx < len(self._rows)):
            return
        r = self._rows[idx]
        n_rows = r["count"]
        if QMessageBox.warning(
                self, "Delete this Cost Centre string?",
                f"This permanently deletes all <b>{n_rows} sales "
                f"voucher(s)</b> that used <b>{r['raw']}</b>.<br><br>"
                "The MIS revenue for those invoices will be gone. This "
                "cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        resolution.delete_unmapped_cc_string_rows(r["raw"])
        self.reload()

    def _bulk_delete(self) -> None:
        indices = sorted({i.row() for i in self.table.selectedIndexes()})
        if not indices:
            return
        raws = [self._rows[i]["raw"] for i in indices]
        total_rows = sum(self._rows[i]["count"] for i in indices)
        if QMessageBox.warning(
                self, f"Delete {len(raws)} Cost Centre strings?",
                f"Permanently delete all <b>{total_rows} sales "
                f"voucher(s)</b> across <b>{len(raws)} string(s)</b>?"
                "<br><br>This cannot be undone.",
                QMessageBox.Cancel | QMessageBox.Yes,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        for raw in raws:
            resolution.delete_unmapped_cc_string_rows(raw)
        self.reload()


# --- Voucher review tab ------------------------------------------------------

class VoucherTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._all_rows: list[dict] = []   # everything from the DB query
        self._rows: list[dict] = []       # post-filter, what the table shows
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Every voucher's amount can be split across cost centres, "
            "managers and services. Use the filters to narrow down what you "
            "need; click <b>Edit splits →</b> on any row to adjust its "
            "attribution.")
        intro.setObjectName("pageNote")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # --- row 1: DB-side filters (Entity / Period / Kind) ---------------
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.entity_combo = NoScrollComboBox()
        self.period_combo = NoScrollComboBox()
        self.kind_combo = NoScrollComboBox()
        self.kind_combo.addItem("All kinds", None)
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

        # --- row 2: in-Python filters (Status + Search) --------------------
        bar2 = QHBoxLayout()
        bar2.setSpacing(8)
        self.status_combo = NoScrollComboBox()
        self.status_combo.addItem("All statuses", None)
        self.status_combo.addItem("⚠ Needs fix only", "needs_fix")
        self.status_combo.addItem("✓ OK only", "ok")
        self.status_combo.currentIndexChanged.connect(self._refilter)
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search by party / client / voucher no…")
        self._sched_filter, self._search_timer = debounced(
            self._refilter, ms=200)
        self.search.textChanged.connect(self._sched_filter)
        bar2.addWidget(QLabel("Status:"))
        bar2.addWidget(self.status_combo)
        bar2.addWidget(self.search, 1)
        layout.addLayout(bar2)

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
        # Entity combo — use the entity name as the visible label and the id
        # as the user data. (Was inverted before, hence the numbers showing.)
        keep_e = self.entity_combo.currentData()
        self.entity_combo.clear()
        self.entity_combo.addItem("(all entities)", None)
        for entity_id, name in repo.fk_options("entities"):
            self.entity_combo.addItem(name, entity_id)
        pos = self.entity_combo.findData(keep_e)
        if pos >= 0:
            self.entity_combo.setCurrentIndex(pos)

        # Period combo — string label = string data.
        keep_p = self.period_combo.currentData()
        self.period_combo.clear()
        self.period_combo.addItem("(all periods)", None)
        for p in vsvc.list_periods():
            self.period_combo.addItem(p, p)
        pos = self.period_combo.findData(keep_p)
        if pos >= 0:
            self.period_combo.setCurrentIndex(pos)

        self._loading = False
        self.reload()

    def reload(self) -> None:
        """Re-fetch from the DB (entity / period / kind filters) and then
        refilter in Python (status + search)."""
        if self._loading:
            return
        self._all_rows = vsvc.list_vouchers(
            self.entity_combo.currentData(),
            self.period_combo.currentData(),
            self.kind_combo.currentData())
        self._refilter()

    def _refilter(self) -> None:
        """Apply status + search to the already-fetched rows. Cheap — runs
        on every keystroke without re-hitting the DB."""
        rows = list(self._all_rows)
        status = self.status_combo.currentData()
        if status == "needs_fix":
            rows = [v for v in rows if v.get("n_unassigned")]
        elif status == "ok":
            rows = [v for v in rows if not v.get("n_unassigned")]
        q = self.search.text().strip().lower()
        if q:
            rows = [v for v in rows
                    if q in (v.get("party_name") or "").lower()
                    or q in (v.get("client_name") or "").lower()
                    or q in (v.get("vch_no") or "").lower()]
        self._rows = rows

        n = len(self._rows)
        total = len(self._all_rows)
        unassigned = self.count()
        parts = [f"{n} voucher{'s' if n != 1 else ''}"]
        if n != total:
            parts.append(f"<span style='color:#64748B;'>of {total}</span>")
        if unassigned:
            parts.append(
                f"<span style='color:#B91C1C;'>{unassigned} unassigned</span>")
        self.summary.setText("  ·  ".join(parts))
        self.empty.setVisible(n == 0)
        self.table.setVisible(n > 0)
        if n == 0:
            return

        rows_body = []
        labels = []
        for v in self._rows:
            rows_body.append([
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
            rows_body,
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
        self.refresh()

    def refresh(self) -> None:
        """Apply auto-mappings + reload every tab from the DB.

        Called on ``showEvent`` (operator navigates to the page) and also
        fired by the Import page after every successful Tally pull or
        Excel commit, so newly-imported vouchers / clients / CC strings
        appear immediately without the operator having to re-navigate.
        """
        resolution.apply_known_client_aliases()
        resolution.apply_known_cc_string_mappings()
        resolution.auto_match_cc_strings()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "_reload_filters"):
                tab._reload_filters()
            elif hasattr(tab, "reload"):
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
