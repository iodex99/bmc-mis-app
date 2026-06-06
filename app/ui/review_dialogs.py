"""Dialogs used by the Review & Map page (Phase 4)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .. import repository as repo
from ..database import transaction
from ..services import resolution
from ..services import vouchers as vsvc
from ..util import fmt_inr
from .widgets import NoScrollComboBox, NoScrollSpinBox


def _combo(options: list[tuple[int, str]], current=None,
           allow_none: bool = True, none_label: str = "—") -> QComboBox:
    cb = NoScrollComboBox()
    if allow_none:
        cb.addItem(none_label, None)
    for oid, label in options:
        cb.addItem(label, oid)
    if current is not None:
        idx = cb.findData(current)
        if idx >= 0:
            cb.setCurrentIndex(idx)
    return cb


# --- Resolve a client --------------------------------------------------------

class ResolveClientDialog(QDialog):
    """Link a raw client name to an existing client or create a new one."""

    def __init__(self, raw: str, parent=None) -> None:
        super().__init__(parent)
        self.raw = raw
        self.setWindowTitle("Resolve Client")
        self.setMinimumWidth(460)
        self._result: tuple | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Raw name from file:\n<b>{raw}</b>"))

        self.link_radio = QRadioButton("Link to an existing client:")
        self.link_radio.setChecked(True)
        layout.addWidget(self.link_radio)

        suggestions = resolution.client_suggestions(raw)
        seen = {cid for cid, _n, _s in suggestions}
        opts = [(cid, f"{name}   ({score}% match)")
                for cid, name, score in suggestions]
        opts += [(cid, name) for cid, name in repo.fk_options("clients")
                 if cid not in seen]
        self.existing_combo = _combo(opts, allow_none=False)
        layout.addWidget(self.existing_combo)

        self.create_radio = QRadioButton("Create a new client:")
        layout.addWidget(self.create_radio)
        form = QFormLayout()
        self.name_edit = QLineEdit(raw)
        # If the Tally Sales Register already told us the partner for this
        # client (via the Cost Center column → cc-string mapping), pre-select
        # it. The operator can change it before saving.
        suggested_cc = resolution.suggest_cc_for_raw_client(raw)
        self.cc_combo = _combo(
            repo.fk_options("cost_centres"),
            current=suggested_cc,
            none_label="(unassigned)")
        form.addRow("Client name:", self.name_edit)
        form.addRow("Cost centre:", self.cc_combo)
        if suggested_cc is not None:
            note = QLabel(
                "<span style='color:#166534;'>✓ Cost centre inferred from the "
                "Sales Register's Cost Center column. Change it if needed.</span>")
            note.setWordWrap(True)
            form.addRow("", note)
        else:
            form.addRow("", QLabel("New clients without a cost centre can be set later."))
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if self.link_radio.isChecked():
            cid = self.existing_combo.currentData()
            if cid is None:
                QMessageBox.warning(self, "Select a client",
                                    "No existing client to link to.")
                return
            self._result = ("link", cid)
        else:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Name required",
                                    "Enter a name for the new client.")
                return
            self._result = ("create", name, self.cc_combo.currentData())
        self.accept()

    def apply(self) -> int:
        """Carry out the chosen action; return rows linked."""
        if not self._result:
            return 0
        if self._result[0] == "link":
            return resolution.link_client(self.raw, self._result[1])
        resolution.create_client(self.raw, self._result[1], self._result[2])
        return 1


# --- Resolve an employee -----------------------------------------------------

class ResolveEmployeeDialog(QDialog):
    """Link a raw employee name to an existing employee or create a new one."""

    def __init__(self, raw: str, parent=None) -> None:
        super().__init__(parent)
        self.raw = raw
        self.setWindowTitle("Resolve Employee")
        self.setMinimumWidth(460)
        self._result: tuple | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Raw name from file:\n<b>{raw}</b>"))

        self.link_radio = QRadioButton("Link to an existing employee:")
        layout.addWidget(self.link_radio)
        suggestions = resolution.employee_suggestions(raw)
        seen = {eid for eid, _n, _s in suggestions}
        opts = [(eid, f"{name}   ({score}% match)")
                for eid, name, score in suggestions]
        opts += [(eid, name) for eid, name in repo.fk_options("employees")
                 if eid not in seen]
        self.existing_combo = _combo(opts, allow_none=False)
        layout.addWidget(self.existing_combo)

        self.create_radio = QRadioButton("Create a new employee:")
        self.create_radio.setChecked(True)
        layout.addWidget(self.create_radio)
        form = QFormLayout()
        self.name_edit = QLineEdit(raw)
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Employee", "CA Article", "CMA Article"])
        self.mgr_combo = _combo(repo.fk_options("managers"), none_label="(none)")
        self.cc_combo = _combo(repo.fk_options("cost_centres"), none_label="(none)")
        form.addRow("Name:", self.name_edit)
        form.addRow("Category:", self.cat_combo)
        form.addRow("Manager:", self.mgr_combo)
        form.addRow("Cost centre:", self.cc_combo)
        layout.addLayout(form)

        if not opts:
            self.link_radio.setEnabled(False)
            self.existing_combo.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if self.link_radio.isChecked():
            eid = self.existing_combo.currentData()
            if eid is None:
                QMessageBox.warning(self, "Select an employee", "Nothing to link to.")
                return
            self._result = ("link", eid)
        else:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Name required", "Enter a name.")
                return
            self._result = ("create", name, self.cat_combo.currentText(),
                            self.mgr_combo.currentData(), self.cc_combo.currentData())
        self.accept()

    def apply(self) -> None:
        if not self._result:
            return
        if self._result[0] == "link":
            resolution.link_employee(self.raw, self._result[1])
        else:
            _a, name, cat, mgr, cc = self._result
            resolution.create_employee(self.raw, name, cat, mgr, cc)


# --- Resolve a Cost Centre string -------------------------------------------

class ResolveCcStringDialog(QDialog):
    """Map a raw Tally Cost Centre string to a (partner, manager) pair."""

    def __init__(self, raw: str, parent=None) -> None:
        super().__init__(parent)
        self.raw = raw
        self.setWindowTitle("Resolve Cost Centre")
        self.setMinimumWidth(440)
        self._result: tuple | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Cost Centre string from Tally:\n<b>{raw}</b>"))

        # Pre-fill the partner / manager combos with whatever our matcher
        # would suggest for this raw string. Lower threshold (50) than the
        # auto-apply path so weaker but still-plausible matches surface
        # here for the operator to confirm — they always see the
        # suggested partner highlighted and only have to click Save.
        suggested_cc, suggested_mgr, score = resolution.suggest_for_raw_cc(
            raw, min_score=50)

        form = QFormLayout()
        # Partner cost centres only (Office is for overheads, not invoices).
        partner_opts = self._partner_options()
        self.cc_combo = _combo(partner_opts,
                                current=suggested_cc, allow_none=False)
        form.addRow("Partner (cost centre):", self.cc_combo)

        mgr_row = QHBoxLayout()
        self.mgr_combo = _combo(repo.fk_options("managers"),
                                 current=suggested_mgr,
                                 none_label="(none / partner only)")
        new_mgr_btn = QPushButton("+ New manager…")
        new_mgr_btn.clicked.connect(self._add_manager)
        mgr_row.addWidget(self.mgr_combo, 1)
        mgr_row.addWidget(new_mgr_btn)
        form.addRow("Manager:", mgr_row)

        layout.addLayout(form)
        if suggested_cc is not None:
            hint = QLabel(
                f"<span style='color:#166534;'>✓ Pre-filled from fuzzy match "
                f"(confidence {score}%). Change if it's the wrong partner."
                f"</span>")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        layout.addWidget(QLabel(
            "<span style='color:#64748B;'>This mapping is remembered; future "
            "imports auto-resolve the same Cost Centre string.</span>"))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _partner_options() -> list[tuple[int, str]]:
        with transaction() as conn:
            return [(r["id"], f"{r['code']} — {r['name']}") for r in conn.execute(
                "SELECT id, code, name FROM cost_centres "
                "WHERE active = 1 AND cc_type = 'partner' ORDER BY code")]

    def _add_manager(self) -> None:
        from .master_data import RecordDialog, SPECS
        spec = next(s for s in SPECS if s.table == "managers")
        dlg = RecordDialog(spec, None, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                repo.insert("managers", dlg.values())
            except Exception as exc:
                QMessageBox.critical(self, "Couldn't add", str(exc))
                return
            # Refresh manager combo, keeping current selection if still present.
            keep = self.mgr_combo.currentData()
            self.mgr_combo.clear()
            self.mgr_combo.addItem("(none / partner only)", None)
            for mid, label in repo.fk_options("managers"):
                self.mgr_combo.addItem(label, mid)
            if keep is not None:
                idx = self.mgr_combo.findData(keep)
                if idx >= 0:
                    self.mgr_combo.setCurrentIndex(idx)
            # Auto-select the just-created manager (last in the list).
            self.mgr_combo.setCurrentIndex(self.mgr_combo.count() - 1)

    def _accept(self) -> None:
        cc = self.cc_combo.currentData()
        if cc is None:
            QMessageBox.warning(self, "Partner required",
                                "Pick a partner cost centre.")
            return
        self._result = (cc, self.mgr_combo.currentData())
        self.accept()

    def apply(self) -> int:
        if not self._result:
            return 0
        cc_id, mgr_id = self._result
        return resolution.map_cc_string(self.raw, cc_id, mgr_id)


# --- Voucher split editor ----------------------------------------------------

class SplitEditorDialog(QDialog):
    """Split a voucher and assign each part a 'Partner - Manager' + service."""

    COLS = ["Amount", "Cost Centre (Partner)", "Manager", "Service", "Note"]

    def __init__(self, voucher: dict, parent=None) -> None:
        super().__init__(parent)
        self.voucher = voucher
        self.net = float(voucher["net_amount"] or 0)
        self.setWindowTitle(f"Voucher #{voucher['id']} — Split & Attribute")
        self.resize(820, 420)

        self._cc = repo.fk_options("cost_centres")
        self._mgr = repo.fk_options("managers")
        self._svc = repo.fk_options("services")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<b>{voucher.get('party_name', '')}</b>  ·  "
            f"{voucher.get('vch_no', '')}  ·  "
            f"net amount <b>{fmt_inr(self.net, 2)}</b>"))

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        bar = QHBoxLayout()
        add_btn = QPushButton("＋ Add split")
        del_btn = QPushButton("Remove selected")
        add_btn.clicked.connect(lambda: self._add_row())
        del_btn.clicked.connect(self._remove_row)
        self.total_lbl = QLabel()
        bar.addWidget(add_btn)
        bar.addWidget(del_btn)
        bar.addStretch(1)
        bar.addWidget(self.total_lbl)
        layout.addLayout(bar)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        existing = vsvc.get_splits(voucher["id"])
        for s in existing or [{"amount": self.net}]:
            self._add_row(s)
        self._update_total()

    # -- row helpers ---------------------------------------------------------
    def _add_row(self, data: dict | None = None) -> None:
        data = data or {}
        r = self.table.rowCount()
        self.table.insertRow(r)

        amount = QDoubleSpinBox()
        amount.setRange(-1e12, 1e12)
        amount.setDecimals(2)
        amount.setGroupSeparatorShown(True)
        amount.wheelEvent = lambda e: e.ignore()
        amount.setValue(float(data.get("amount", self._remaining())))
        amount.valueChanged.connect(self._update_total)
        self.table.setCellWidget(r, 0, amount)

        # Pre-fill CC + manager from the raw Tally string when the split
        # doesn't already have them resolved. This is what turns most
        # 'needs fix' vouchers into one-click 'OK' confirmations — the
        # operator just clicks Save instead of picking from 8 partners.
        cc_id = data.get("cost_centre_id")
        mgr_id = data.get("manager_id")
        svc_id = data.get("service_id")
        raw_cc = (data.get("raw_cost_centre") or "").strip()
        suggested = False
        if cc_id is None and raw_cc:
            s_cc, s_mgr, _score = resolution.suggest_for_raw_cc(raw_cc)
            if s_cc is not None:
                cc_id = s_cc
                mgr_id = mgr_id or s_mgr
                suggested = True

        cc_combo = _combo(self._cc, cc_id, none_label="(choose)")
        mgr_combo = _combo(self._mgr, mgr_id, none_label="(none)")
        svc_combo = _combo(self._svc, svc_id, none_label="(none)")
        if suggested:
            # Italic hint so the operator sees this row's CC was auto-
            # suggested from Tally's CC text and not yet confirmed.
            tip = f'Suggested from Tally CC: "{raw_cc}". Confirm or change.'
            cc_combo.setToolTip(tip)
            mgr_combo.setToolTip(tip)
            f = cc_combo.font()
            f.setItalic(True)
            cc_combo.setFont(f)
            mgr_combo.setFont(f)
        self.table.setCellWidget(r, 1, cc_combo)
        self.table.setCellWidget(r, 2, mgr_combo)
        self.table.setCellWidget(r, 3, svc_combo)

        # Show the raw Tally CC in the note column when present so the
        # operator can see what Tally said even if they overrode it.
        note_text = data.get("note") or ""
        if raw_cc and not note_text:
            note_text = f"Tally CC: {raw_cc}"
        note = QLineEdit(note_text)
        self.table.setCellWidget(r, 4, note)
        self._update_total()

    def _remove_row(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        for r in sorted(rows, reverse=True):
            self.table.removeRow(r)
        self._update_total()

    def _remaining(self) -> float:
        return round(self.net - self._sum(), 2)

    def _sum(self) -> float:
        total = 0.0
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if w:
                total += w.value()
        return total

    def _update_total(self) -> None:
        diff = round(self.net - self._sum(), 2)
        msg = (f"Allocated: {fmt_inr(self._sum(), 2)}   /   "
               f"Net: {fmt_inr(self.net, 2)}")
        if abs(diff) > 0.01:
            msg += f"   ⚠ unallocated {fmt_inr(diff, 2)}"
        self.total_lbl.setText(msg)

    # -- save ----------------------------------------------------------------
    def _save(self) -> None:
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No splits", "Add at least one split.")
            return
        if abs(round(self.net - self._sum(), 2)) > 1.0:
            QMessageBox.warning(
                self, "Amounts do not balance",
                "The split amounts must add up to the voucher's net amount.")
            return
        splits = []
        for r in range(self.table.rowCount()):
            splits.append({
                "amount": self.table.cellWidget(r, 0).value(),
                "cost_centre_id": self.table.cellWidget(r, 1).currentData(),
                "manager_id": self.table.cellWidget(r, 2).currentData(),
                "service_id": self.table.cellWidget(r, 3).currentData(),
                "note": self.table.cellWidget(r, 4).text().strip() or None,
            })
        vsvc.save_splits(self.voucher["id"], splits)
        self.accept()
