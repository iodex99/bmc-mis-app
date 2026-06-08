"""Import Files page — upload, map, preview and commit a file (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config, repository as repo
from ..importing import commit, excel_reader, parsers, sniffer, templates
from ..services import resolution
from ..util import fmt_inr
from .column_mapping import ColumnMappingDialog
from .tally_pull import TallyPullWidget

_FILE_TYPE_LABELS = {
    config.FILE_TYPE_SALES: "Tally — Sales Register",
    config.FILE_TYPE_PURCHASE: "Tally — Purchase Register",
    config.FILE_TYPE_TIMESHEET: "Timesheet",
    config.FILE_TYPE_SALARY: "Salary & Reimbursements",
}


class ImportPage(QWidget):
    """Drives the choose → map → preview → commit import workflow."""

    # Fires after any successful Tally pull OR Excel-upload commit, so the
    # MainWindow can ask the Review page to refresh.
    imported = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._path: Path | None = None
        self._grid: list[list] = []
        self._mapping: dict | None = None
        self._signature: str = ""
        self._result = None

        # The page is taller than the window once both the Tally pull section
        # and the Excel fallback are visible, so wrap the whole thing in a
        # scroll area.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)

        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        heading = QLabel("Import Files")
        heading.setObjectName("pageHeading")
        outer.addWidget(heading)
        note = QLabel(
            "Recommended: export the Sales / Purchase Register from Tally as "
            "an Excel file and upload it below. Each ledger line keeps its "
            "own cost-centre tag, so partner + manager are picked up directly "
            "from the file. The Tally HTTP pull is a convenience for setups "
            "whose Tally configuration exposes per-line cost centres over the "
            "gateway — many installations don't, in which case stick with the "
            "Excel upload.")
        note.setObjectName("pageNote")
        note.setWordWrap(True)
        outer.addWidget(note)

        # --- Excel upload (recommended) ------------------------------------
        fallback_box = QGroupBox("Upload an Excel file (recommended)")
        fb = QVBoxLayout(fallback_box)
        fb.setSpacing(8)
        fb_note = QLabel(
            "Sales / Purchase Registers exported from Tally are auto-detected "
            "from their headers; new layouts only need column mapping once. "
            "Multi-service vouchers and per-line cost-centre tags carry "
            "through to the MIS without manual splitting.")
        fb_note.setWordWrap(True)
        fb_note.setObjectName("pageNote")
        fb.addWidget(fb_note)
        # Everything that follows is the original Excel-upload UI. Layouts
        # below build into ``fb`` instead of the page root.
        outer.addWidget(fallback_box)
        # Keep ``root`` referencing the inner layout so the rest of the file
        # builds into the fallback box without further edits.
        root = fb

        # --- selectors ------------------------------------------------------
        form = QFormLayout()
        self.type_combo = QComboBox()
        for key, label in _FILE_TYPE_LABELS.items():
            self.type_combo.addItem(label, key)
        form.addRow("File type:", self.type_combo)

        self.entity_combo = QComboBox()
        self._reload_entities()
        form.addRow("Entity:", self.entity_combo)

        self.sheet_combo = QComboBox()
        self.sheet_combo.currentIndexChanged.connect(self._load_sheet)
        self.sheet_combo.setEnabled(False)
        form.addRow("Worksheet:", self.sheet_combo)
        root.addLayout(form)

        # --- action buttons -------------------------------------------------
        bar = QHBoxLayout()
        self.choose_btn = QPushButton("Choose Excel file…")
        self.map_btn = QPushButton("Map / Re-map Columns")
        self.commit_btn = QPushButton("Commit Import")
        self.commit_btn.setObjectName("primary")
        self.choose_btn.clicked.connect(self._choose_file)
        self.map_btn.clicked.connect(self._map_columns)
        self.commit_btn.clicked.connect(self._commit)
        self.map_btn.setEnabled(False)
        self.commit_btn.setEnabled(False)
        bar.addWidget(self.choose_btn)
        bar.addWidget(self.map_btn)
        bar.addWidget(self.commit_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        self.status = QLabel("No file chosen.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        # --- parsed preview -------------------------------------------------
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setMaximumHeight(220)
        root.addWidget(self.preview)

        # --- Tally HTTP pull (secondary) -----------------------------------
        # Kept available for installs whose Tally exposes per-line cost
        # centres over the gateway. For setups that don't (most do not),
        # the Excel-upload path above is the right primary flow.
        self.tally_pull = TallyPullWidget()
        self.tally_pull.imported.connect(self._reload_recent)
        self.tally_pull.imported.connect(self.imported)
        outer.addWidget(self.tally_pull)

        # Recent-imports table sits at the bottom of the page, covering both
        # Tally pulls and Excel uploads.
        outer.addWidget(QLabel("Recent imports:"))
        self.recent = QTableWidget()
        self.recent.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent.setMaximumHeight(180)
        outer.addWidget(self.recent)
        self._reload_recent()

    # -- helpers -------------------------------------------------------------
    def showEvent(self, event):  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self._reload_entities()
        self._reload_recent()

    def _reload_entities(self) -> None:
        current = self.entity_combo.currentData() if self.entity_combo.count() else None
        self.entity_combo.clear()
        self.entity_combo.addItem("(not specified)", None)
        for eid, name in repo.fk_options("entities"):
            self.entity_combo.addItem(name, eid)
        if current is not None:
            pos = self.entity_combo.findData(current)
            if pos >= 0:
                self.entity_combo.setCurrentIndex(pos)

    @property
    def file_type(self) -> str:
        return self.type_combo.currentData()

    # -- workflow ------------------------------------------------------------
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Excel file", "", "Excel files (*.xlsx *.xls)")
        if not path:
            return
        self._path = Path(path)
        try:
            sheets = excel_reader.sheet_names(path)
        except Exception as exc:
            QMessageBox.critical(self, "Could not open file", str(exc))
            return
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(sheets)
        self.sheet_combo.setEnabled(True)
        self.sheet_combo.blockSignals(False)
        self._load_sheet()

    def _load_sheet(self) -> None:
        if not self._path or self.sheet_combo.count() == 0:
            return
        try:
            self._grid = excel_reader.read_grid(
                self._path, self.sheet_combo.currentText())
        except Exception as exc:
            QMessageBox.critical(self, "Could not read sheet", str(exc))
            return
        self.map_btn.setEnabled(True)
        self.commit_btn.setEnabled(False)
        self._result = None
        guess = excel_reader.guess_header_row(self._grid)
        self._signature = templates.layout_signature(self._grid, guess)

        # 1. Voucher-dump sniffer — handles the "actual" Tally export format
        #    automatically. If the file's headers fingerprint as a Tally
        #    voucher-dump (Date + Particulars + Vch No + Debit + Credit),
        #    we bypass the column-mapping dialog entirely and parse straight
        #    away. Column positions can differ between entities and Tally
        #    versions; the sniffer reads them from the header text.
        ft = self.file_type
        if ft in (config.FILE_TYPE_SALES, config.FILE_TYPE_PURCHASE):
            sniffed = sniffer.sniff(self._grid)
            if sniffed:
                # If the banner says "Sales/Purchase Register" and disagrees
                # with the file-type dropdown, prefer the banner — the
                # operator may have picked the wrong type by mistake.
                if sniffed["kind"] and sniffed["kind"] != ft:
                    pos = self.type_combo.findData(sniffed["kind"])
                    if pos >= 0:
                        self.type_combo.setCurrentIndex(pos)
                self._mapping = {
                    "header_row": sniffed["header_row"],
                    "columns": sniffed["colmap"],
                }
                self.status.setText(
                    f"{self._path.name} — auto-detected voucher-dump layout "
                    f"(header on row {sniffed['header_row'] + 1}).")
                self._parse_and_preview()
                return

        # 2. Template cache — used by the wide-flat sales format and the
        #    timesheet / salary sheets.
        saved = templates.find_template(self.file_type, self._signature)
        if saved:
            self._mapping = saved
            self.status.setText(
                f"{self._path.name} — known layout, mapping reused automatically.")
            self._parse_and_preview()
        else:
            self._mapping = None
            self.status.setText(
                f"{self._path.name} — new layout. Click 'Map / Re-map Columns'.")
            self.preview.clear()
            self.preview.setRowCount(0)

    def _map_columns(self) -> None:
        if not self._grid:
            return
        dlg = ColumnMappingDialog(self._grid, self.file_type, self._mapping, self)
        if dlg.exec() != ColumnMappingDialog.Accepted:
            return
        columns = dlg.column_map()
        header_row = dlg.header_index()
        service_map = dlg.service_map()
        tax_cols = dlg.tax_cols()
        templates.save_template(
            self.file_type, self._signature, header_row, columns,
            service_map=service_map, tax_cols=tax_cols)
        self._mapping = {
            "header_row": header_row, "columns": columns,
            "service_map": service_map, "tax_cols": tax_cols,
        }
        self._parse_and_preview()

    def _parse_and_preview(self) -> None:
        if not self._mapping:
            return
        # service_map keys come back from JSON as strings — convert to int.
        sm_raw = self._mapping.get("service_map") or {}
        service_map = {int(k): v for k, v in sm_raw.items()}
        tax_cols = [int(c) for c in (self._mapping.get("tax_cols") or [])]
        self._result = parsers.parse(
            self.file_type, self._grid, self._mapping["columns"],
            self._mapping["header_row"] + 1,
            service_map=service_map, tax_cols=tax_cols)
        res = self._result
        msg = f"Parsed {res.row_count} record(s)."
        if res.warnings:
            msg += "  ⚠ " + "  ".join(res.warnings)
        self.status.setText(msg)
        self.commit_btn.setEnabled(res.row_count > 0)
        self._render_preview(res)

    def _render_preview(self, res) -> None:
        if res.vouchers:
            cols = ["Date", "Vch No.", "Party", "Net Amount", "Tax",
                    "Cost Centre (raw)", "Description"]
            rows = [[str(v.date or ""), v.vch_no, v.party_name,
                     fmt_inr(v.net_amount), fmt_inr(v.tax_amount),
                     v.raw_cost_centre, v.description] for v in res.vouchers]
        elif res.timesheet:
            cols = ["Employee", "Date", "Client", "Task", "Hours",
                    "Reporting Manager", "Billable"]
            rows = [[t.emp_name, str(t.date or ""), t.client_raw, t.task,
                     f"{t.hours:.2f}", t.reporting_manager,
                     "Yes" if t.is_billable else "No"] for t in res.timesheet]
        else:
            cols = ["Period", "Employee", "Cost Centre", "Entity", "Category",
                    "Salary Paid", "Reimbursement"]
            rows = [[s.period or "", s.employee_name, s.raw_cost_centre,
                     s.raw_entity, s.category, fmt_inr(s.salary_paid, 2),
                     fmt_inr(s.reimbursement, 2)] for s in res.salary]

        self.preview.setColumnCount(len(cols))
        self.preview.setHorizontalHeaderLabels(cols)
        shown = rows[:200]
        self.preview.setRowCount(len(shown))
        for r, row in enumerate(shown):
            for c, val in enumerate(row):
                self.preview.setItem(r, c, QTableWidgetItem(str(val)))
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.preview.horizontalHeader().setStretchLastSection(True)

    def _commit(self) -> None:
        if not self._result:
            return
        entity_id = self.entity_combo.currentData()
        from ..importing.commit import _dominant_period
        period = _dominant_period(self._result)
        prior = commit.existing_batch(entity_id, self.file_type, period)
        if prior:
            # An existing batch is only an issue if the new file isn't just a
            # re-upload of the same data. Dedup runs anyway — let the user
            # proceed if they want; the dedup count tells them what happened.
            if QMessageBox.question(
                    self, "Already imported",
                    f"A {self.file_type} import for this entity/period already "
                    f"exists ('{prior['file_name']}', {prior['imported_at']}).\n\n"
                    "Continue? Vouchers with a matching voucher number will be "
                    "skipped automatically.") != QMessageBox.Yes:
                return
        try:
            report = commit.commit_result(
                self._result, entity_id, self._path.name)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        # Auto-resolve any names this import already has saved aliases for.
        auto_linked = resolution.apply_known_client_aliases()
        cc_linked = resolution.apply_known_cc_string_mappings()
        unmapped_c = len(resolution.unresolved_clients())
        unmapped_e = len(resolution.unresolved_employees())
        unmapped_cc = len(resolution.unresolved_cc_strings())

        head_lines = [
            f"Import committed — batch #{report.batch_id}.",
            f"  • {fmt_inr(report.new_vouchers)} new voucher(s) added.",
        ]
        if report.skipped_duplicates:
            head_lines.append(
                f"  • {fmt_inr(report.skipped_duplicates)} duplicate "
                "voucher(s) skipped (same voucher number, same amount).")
        if report.amount_mismatches:
            head_lines.append(
                f"  ⚠ {fmt_inr(len(report.amount_mismatches))} voucher(s) "
                "had a matching number but a different amount — they were "
                "skipped. Review the prior batch in Records if needed.")
        if report.timesheet_rows:
            head_lines.append(
                f"  • {fmt_inr(report.timesheet_rows)} timesheet row(s) added.")
        if report.salary_rows:
            head_lines.append(
                f"  • {fmt_inr(report.salary_rows)} salary row(s) added.")
        head = "\n".join(head_lines)

        auto_total = auto_linked + cc_linked
        if auto_total:
            head += (f"\n\n{fmt_inr(auto_total)} row(s) auto-mapped from "
                     "previously remembered names.")

        if unmapped_c or unmapped_e or unmapped_cc:
            parts = []
            if unmapped_cc:
                parts.append(f"{fmt_inr(unmapped_cc)} cost-centre string(s)")
            if unmapped_c:
                parts.append(f"{fmt_inr(unmapped_c)} client name(s)")
            if unmapped_e:
                parts.append(f"{fmt_inr(unmapped_e)} employee name(s)")
            msg = (f"{head}\n\n"
                   + ", ".join(parts) +
                   " still need to be mapped.\n\nResolve them now?")
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("Imported — mapping needed")
            box.setText(msg)
            yes = box.addButton("Resolve now", QMessageBox.AcceptRole)
            box.addButton("Later", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is yes:
                win = self.window()
                if hasattr(win, "nav"):
                    win.nav.setCurrentRow(2)        # Review & Map (index 2)
        else:
            QMessageBox.information(
                self, "Imported",
                head + "\n\nAll names auto-mapped — head to 'Generate MIS' "
                "when ready.")

        self.commit_btn.setEnabled(False)
        self._reload_recent()
        self.imported.emit()

    def _reload_recent(self) -> None:
        batches = repo.fetch_all("import_batches", order_by="id DESC")[:30]
        ent = repo.fk_label_map("entities")
        cols = ["#", "Type", "Entity", "Period", "File", "Imported", "Status"]
        self.recent.setColumnCount(len(cols))
        self.recent.setHorizontalHeaderLabels(cols)
        self.recent.setRowCount(len(batches))
        for r, b in enumerate(batches):
            values = [b["id"], b["file_type"], ent.get(b["entity_id"], "—"),
                      b["period"] or "—", b["file_name"] or "",
                      b["imported_at"], b["status"]]
            for c, v in enumerate(values):
                self.recent.setItem(r, c, QTableWidgetItem(str(v)))
        self.recent.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.recent.horizontalHeader().setStretchLastSection(True)
