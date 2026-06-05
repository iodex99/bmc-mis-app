"""Pull-from-Tally widget — primary import path.

Hosts inside the Import Files page above the Excel-upload section. The
operator opens a company in Tally on the same PC, picks a date range, and
clicks one button — the widget probes Tally, fetches the Day Book, runs
the same commit + dedup + auto-mapping flow Excel uploads use, and shows
a one-line summary. Failures fall back gracefully to the Excel section.
"""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import repository as repo
from ..importing import commit, tally_client, tally_xml
from ..services import resolution
from ..util import fmt_inr


# ---------------- background fetch (so the UI doesn't freeze) ---------------

class _PullWorker(QObject):
    """Run :func:`tally_client.fetch_day_book` off the UI thread."""

    finished = Signal(object, object)   # (ParseResult | None, error | None)

    def __init__(self, from_date, to_date, company, url):
        super().__init__()
        self._from = from_date
        self._to = to_date
        self._company = company
        self._url = url

    def run(self):
        try:
            result = tally_client.fetch_day_book(
                self._from, self._to,
                company_name=self._company or None,
                url=self._url or None)
            self.finished.emit(result, None)
        except Exception as exc:                                  # noqa: BLE001
            self.finished.emit(None, exc)


class _ProbeWorker(QObject):
    """Run :func:`tally_client.current_company` off the UI thread."""

    finished = Signal(object, object)

    def __init__(self, url):
        super().__init__()
        self._url = url

    def run(self):
        try:
            cc = tally_client.current_company(url=self._url or None)
            self.finished.emit(cc, None)
        except Exception as exc:                                  # noqa: BLE001
            self.finished.emit(None, exc)


# ----------------------------- widget --------------------------------------

class TallyPullWidget(QGroupBox):
    """Self-contained widget — drop it into any layout."""

    imported = Signal()    # emitted after a successful pull+commit

    def __init__(self) -> None:
        super().__init__("Pull from Tally  (primary)")
        self.setObjectName("tallyPull")
        self._worker: _PullWorker | None = None
        self._worker_thread: QThread | None = None
        self._probe_worker: _ProbeWorker | None = None
        self._probe_thread: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        note = QLabel(
            "Open Tally with the right company loaded, pick a date range, "
            "and click <b>Pull</b>. The MIS app fetches voucher data over "
            "Tally's local HTTP gateway — no API key, no internet.")
        note.setWordWrap(True)
        note.setObjectName("pageNote")
        layout.addWidget(note)

        # --- URL row -------------------------------------------------------
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Tally URL:"))
        self.url_edit = QLineEdit(tally_client.get_tally_url())
        self.url_edit.setPlaceholderText(tally_client.DEFAULT_TALLY_URL)
        url_row.addWidget(self.url_edit, 1)
        self.test_btn = QPushButton("Test")
        self.test_btn.clicked.connect(self._test_connection)
        url_row.addWidget(self.test_btn)
        layout.addLayout(url_row)

        self.status = QLabel("Click Test to check the connection.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #555;")
        layout.addWidget(self.status)

        # --- pull controls -------------------------------------------------
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(QLabel("From date:"), 0, 0)
        self.from_date = QDateEdit(calendarPopup=True)
        self.from_date.setDisplayFormat("dd MMM yyyy")
        self.from_date.setDate(_default_from())
        grid.addWidget(self.from_date, 0, 1)

        grid.addWidget(QLabel("To date:"), 0, 2)
        self.to_date = QDateEdit(calendarPopup=True)
        self.to_date.setDisplayFormat("dd MMM yyyy")
        self.to_date.setDate(_default_to())
        grid.addWidget(self.to_date, 0, 3)

        grid.addWidget(QLabel("Map to entity:"), 1, 0)
        self.entity_combo = QComboBox()
        self._reload_entities()
        grid.addWidget(self.entity_combo, 1, 1, 1, 3)
        layout.addLayout(grid)

        # --- pull button + result -----------------------------------------
        bar = QHBoxLayout()
        self.pull_btn = QPushButton("Pull Vouchers from Tally")
        self.pull_btn.setObjectName("primary")
        self.pull_btn.clicked.connect(self._pull)
        bar.addStretch(1)
        bar.addWidget(self.pull_btn)
        layout.addLayout(bar)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("color: #2F7DF6;")
        layout.addWidget(self.result_label)

    # -- entities --------------------------------------------------------

    def _reload_entities(self) -> None:
        current = (self.entity_combo.currentData()
                   if self.entity_combo.count() else None)
        self.entity_combo.clear()
        self.entity_combo.addItem(
            "Auto-detect from Tally", None)
        for eid, name in repo.fk_options("entities"):
            self.entity_combo.addItem(name, eid)
        if current is not None:
            pos = self.entity_combo.findData(current)
            if pos >= 0:
                self.entity_combo.setCurrentIndex(pos)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.url_edit.setText(tally_client.get_tally_url())
        self._reload_entities()

    # -- connection test ------------------------------------------------

    def _test_connection(self) -> None:
        url = self.url_edit.text().strip() or tally_client.DEFAULT_TALLY_URL
        tally_client.set_tally_url(url)
        self.status.setText("Probing Tally…")
        self.status.setStyleSheet("color: #555;")
        self.test_btn.setEnabled(False)

        thread = QThread(self)
        worker = _ProbeWorker(url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_probe_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Keep references so they aren't GC'd before signals fire.
        self._probe_worker = worker
        self._probe_thread = thread
        thread.start()

    def _on_probe_done(self, cc, error) -> None:
        self.test_btn.setEnabled(True)
        if error is not None:
            self.status.setText(f"❌ {error}")
            self.status.setStyleSheet("color: #B33A3A;")
            return
        if cc is None:
            self.status.setText(
                "⚠ Connected to Tally, but no company is loaded. "
                "Open a company in Tally and try again.")
            self.status.setStyleSheet("color: #B07000;")
            return
        books = ""
        if cc.books_from and cc.books_to:
            books = (f" (books: {cc.books_from:%d %b %Y} → "
                     f"{cc.books_to:%d %b %Y})")
        self.status.setText(f"✓ Connected — <b>{cc.name}</b>{books}")
        self.status.setStyleSheet("color: #1B7A1B;")

    # -- pull ------------------------------------------------------------

    def _pull(self) -> None:
        url = self.url_edit.text().strip() or tally_client.DEFAULT_TALLY_URL
        tally_client.set_tally_url(url)
        from_d = self.from_date.date().toPython()
        to_d = self.to_date.date().toPython()
        if from_d > to_d:
            QMessageBox.warning(self, "Invalid range",
                                "From-date is after To-date.")
            return

        self.pull_btn.setEnabled(False)
        self.result_label.setText(
            f"Fetching {from_d:%d %b %Y} → {to_d:%d %b %Y} from Tally…")

        thread = QThread(self)
        worker = _PullWorker(from_d, to_d, None, url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_pull_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _on_pull_done(self, result, error) -> None:
        self.pull_btn.setEnabled(True)
        if error is not None:
            self.result_label.setText(f"❌ {error}")
            self.result_label.setStyleSheet("color: #B33A3A;")
            QMessageBox.critical(self, "Tally pull failed", str(error))
            return
        if not result.vouchers:
            msg = ("No sales or purchase vouchers in that period. Check the "
                   "date range, and make sure Tally has the right company "
                   "loaded.")
            self.result_label.setText(f"⚠ {msg}")
            self.result_label.setStyleSheet("color: #B07000;")
            return

        # Decide entity to commit against. If 'Auto-detect' is selected, ask
        # Tally which company is loaded right now and look that up in our
        # entity master (canonical name OR alias).
        entity_id = self.entity_combo.currentData()
        url = self.url_edit.text().strip() or tally_client.DEFAULT_TALLY_URL
        if entity_id is None:
            try:
                cc = tally_client.current_company(url=url)
            except tally_client.TallyError:
                cc = None
            if cc:
                entity_id = _entity_id_for(cc.name)
            if entity_id is None:
                QMessageBox.warning(
                    self, "No entity match",
                    "Tally's current company doesn't match any entity in "
                    "Master Data. Pick a target entity from the dropdown.")
                return

        # Commit per kind so each batch records the right file_type
        by_kind = tally_xml.split_by_kind(result)
        kinds = []
        for ft, sub_result in by_kind.items():
            label = f"Tally pull {self._period_label()} ({ft})"
            r = commit.commit_result(sub_result, entity_id, label)
            kinds.append((ft, r))

        resolution.apply_known_client_aliases()
        resolution.apply_known_cc_string_mappings()
        unmapped_cc = len(resolution.unresolved_cc_strings())
        unmapped_clients = len(resolution.unresolved_clients())

        lines = []
        for ft, r in kinds:
            seg = (f"<b>{ft.title()}</b>: {fmt_inr(r.new_vouchers)} new")
            if r.skipped_duplicates:
                seg += f", {fmt_inr(r.skipped_duplicates)} duplicate(s) skipped"
            if r.amount_mismatches:
                seg += (f", ⚠ {fmt_inr(len(r.amount_mismatches))} amount "
                        "mismatch(es)")
            lines.append(seg)
        if unmapped_cc or unmapped_clients:
            tail = "Items still needing review: "
            parts = []
            if unmapped_cc:
                parts.append(f"{unmapped_cc} cost-centre string(s)")
            if unmapped_clients:
                parts.append(f"{unmapped_clients} client name(s)")
            tail += ", ".join(parts) + "."
            lines.append(tail)

        self.result_label.setText("<br>".join(lines))
        self.result_label.setStyleSheet("color: #1B7A1B;")
        self.imported.emit()

    # -- helpers --------------------------------------------------------

    def _period_label(self) -> str:
        f = self.from_date.date().toPython()
        t = self.to_date.date().toPython()
        if f.year == t.year and f.month == t.month:
            return f.strftime("%b %Y")
        return f"{f:%d %b %Y}–{t:%d %b %Y}"


def _default_from() -> QDate:
    """Default: first day of the previous calendar month (typical MIS run)."""
    today = _dt.date.today()
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - _dt.timedelta(days=1)
    first_prev_month = last_prev_month.replace(day=1)
    return QDate(first_prev_month.year, first_prev_month.month, 1)


def _default_to() -> QDate:
    today = _dt.date.today()
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - _dt.timedelta(days=1)
    return QDate(last_prev_month.year, last_prev_month.month,
                 last_prev_month.day)


def _entity_id_for(tally_company_name: str) -> int | None:
    """Map a Tally company name to one of our master entities via the same
    alias table the operator uses for ledger names."""
    from ..database import transaction
    key = (tally_company_name or "").strip().lower()
    if not key:
        return None
    with transaction() as conn:
        row = conn.execute(
            "SELECT e.id FROM entities e "
            "LEFT JOIN entity_aliases a ON a.entity_id = e.id "
            "WHERE lower(e.name) = ? OR lower(a.alias) = ?",
            (key, key)).fetchone()
    return row["id"] if row else None
