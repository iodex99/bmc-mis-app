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


def _make_date_edit(default: QDate) -> QDateEdit:
    """A QDateEdit with a properly-sized calendar popup.

    Default Qt calendar columns on Windows + Fusion style sometimes squeeze
    to the point that two-digit day numbers render as ``...``. Forcing a
    minimum width on the underlying ``QCalendarWidget`` (and giving it
    enough breathing room via stylesheet) keeps every cell readable.
    """
    edit = QDateEdit(calendarPopup=True)
    edit.setDisplayFormat("dd MMM yyyy")
    edit.setDate(default)
    edit.setMinimumWidth(140)
    cal = edit.calendarWidget()
    if cal is not None:
        cal.setMinimumWidth(340)
        cal.setMinimumHeight(260)
        cal.setGridVisible(True)
        cal.setStyleSheet(
            "QCalendarWidget QAbstractItemView:enabled {"
            "  background: white; color: #1F2A44;"
            "  selection-background-color: #4F46E5;"
            "  selection-color: white;"
            "  font-size: 11pt;"
            "}"
            "QCalendarWidget QAbstractItemView:disabled { color: #C0C4CC; }"
            "QCalendarWidget QWidget#qt_calendar_navigationbar {"
            "  background: #1F2A44;"
            "}"
            "QCalendarWidget QToolButton {"
            "  color: white; background: transparent;"
            "  padding: 4px 10px;"
            "  font-size: 11pt; font-weight: bold;"
            "}"
            "QCalendarWidget QToolButton::menu-indicator { image: none; }"
            "QCalendarWidget QSpinBox {"
            "  background: white; color: #1F2A44;"
            "  padding: 2px 4px;"
            "}"
        )
    return edit

from .. import repository as repo
from ..importing import commit, tally_client, tally_xml
from ..services import resolution
from ..util import fmt_inr


# ---------------- background fetch (so the UI doesn't freeze) ---------------

class _PullWorker(QObject):
    """Run :func:`tally_client.fetch_day_book` off the UI thread.

    The company name passed here is what the operator explicitly picked
    in the dropdown — it goes through as ``SVCURRENTCOMPANY`` on the Day
    Book request, so Tally is *forced* to use that company regardless of
    which one happens to be in focus in the UI. If the operator left the
    dropdown empty, we probe ``current_company`` as a fallback.
    """

    finished = Signal(object, object, object)  # (ParseResult, company, error)

    def __init__(self, from_date, to_date, company_name, url):
        super().__init__()
        self._from = from_date
        self._to = to_date
        self._company = company_name
        self._url = url

    def run(self):
        try:
            company_name = self._company
            if not company_name:
                cc = tally_client.current_company(url=self._url or None)
                company_name = cc.name if cc else None
            result = tally_client.fetch_day_book(
                self._from, self._to,
                company_name=company_name,
                url=self._url or None)
            self.finished.emit(result, company_name, None)
        except Exception as exc:                                  # noqa: BLE001
            self.finished.emit(None, None, exc)


class _ProbeWorker(QObject):
    """Ask Tally what company is loaded *and* what other companies are open.

    The two queries are bundled so the UI gets the dropdown contents in
    one round-trip after the operator clicks Test.
    """

    finished = Signal(object, object, object)
    # (current_cc, all_companies, error)

    def __init__(self, url):
        super().__init__()
        self._url = url

    def run(self):
        try:
            cc = tally_client.current_company(url=self._url or None)
            try:
                companies = tally_client.list_companies(url=self._url or None)
            except tally_client.TallyError:
                companies = []
            self.finished.emit(cc, companies, None)
        except Exception as exc:                                  # noqa: BLE001
            self.finished.emit(None, [], exc)


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

        # --- Tally company picker -----------------------------------------
        # Editable combo so the operator can either pick from the list
        # we get back from Tally OR type the exact company name manually
        # (useful when Tally's list_companies returns nothing — some Tally
        # builds restrict that collection). Whatever's in the box is what
        # gets sent as SVCURRENTCOMPANY on the pull request.
        co_row = QHBoxLayout()
        co_row.addWidget(QLabel("Tally company:"))
        self.company_combo = QComboBox()
        self.company_combo.setEditable(True)
        self.company_combo.setInsertPolicy(QComboBox.NoInsert)
        self.company_combo.lineEdit().setPlaceholderText(
            "Click Test to list loaded companies, or type the exact "
            "name here")
        co_row.addWidget(self.company_combo, 1)
        layout.addLayout(co_row)

        # --- pull controls -------------------------------------------------
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(QLabel("From date:"), 0, 0)
        self.from_date = _make_date_edit(_default_from())
        grid.addWidget(self.from_date, 0, 1)

        grid.addWidget(QLabel("To date:"), 0, 2)
        self.to_date = _make_date_edit(_default_to())
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

    def _on_probe_done(self, cc, companies, error) -> None:
        self.test_btn.setEnabled(True)
        if error is not None:
            self.status.setText(f"❌ {error}")
            self.status.setStyleSheet("color: #B33A3A;")
            return
        if cc is None and not companies:
            self.status.setText(
                "⚠ Connected to Tally, but no company is loaded. "
                "Open a company in Tally and try again.")
            self.status.setStyleSheet("color: #B07000;")
            return

        # Build the union of {currently-in-focus} ∪ {list_companies result}
        # so the dropdown lists everything Tally is aware of.
        names_in_order: list[str] = []
        seen: set[str] = set()
        if cc and cc.name and cc.name not in seen:
            names_in_order.append(cc.name)
            seen.add(cc.name)
        for c in companies:
            if c.name and c.name not in seen:
                names_in_order.append(c.name)
                seen.add(c.name)

        # Preserve whatever the operator might have typed.
        prior = self.company_combo.currentText().strip()
        self.company_combo.blockSignals(True)
        self.company_combo.clear()
        self.company_combo.addItems(names_in_order)
        if prior and prior in seen:
            self.company_combo.setCurrentText(prior)
        elif cc and cc.name:
            self.company_combo.setCurrentText(cc.name)
        elif prior:
            self.company_combo.setCurrentText(prior)
        self.company_combo.blockSignals(False)

        # Status line with current-focus + how many we'll let the user
        # choose between.
        bits = []
        if cc:
            books = ""
            if cc.books_from and cc.books_to:
                books = (f" (books: {cc.books_from:%d %b %Y} → "
                         f"{cc.books_to:%d %b %Y})")
            bits.append(f"current: <b>{cc.name}</b>{books}")
        extra = max(0, len(names_in_order) - (1 if cc else 0))
        if extra:
            bits.append(f"{extra} other compan{'ies' if extra != 1 else 'y'} "
                        "loaded — pick from the dropdown below")
        if not bits:
            bits.append("connected, but no company info returned")
        self.status.setText("✓ Connected — " + "; ".join(bits))
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

        company_name = self.company_combo.currentText().strip() or None

        self.pull_btn.setEnabled(False)
        if company_name:
            self.result_label.setText(
                f"Fetching {from_d:%d %b %Y} → {to_d:%d %b %Y} from "
                f"<b>{company_name}</b>…")
        else:
            self.result_label.setText(
                f"Fetching {from_d:%d %b %Y} → {to_d:%d %b %Y} from Tally…")

        thread = QThread(self)
        worker = _PullWorker(from_d, to_d, company_name, url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_pull_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _on_pull_done(self, result, company_name, error) -> None:
        self.pull_btn.setEnabled(True)
        if error is not None:
            self.result_label.setText(f"❌ {error}")
            self.result_label.setStyleSheet("color: #B33A3A;")
            QMessageBox.critical(self, "Tally pull failed", str(error))
            return
        if not result.vouchers:
            company_hint = (f" Tally currently has <b>{company_name}</b> "
                            "loaded — make sure that's the right company "
                            "for this period." if company_name else "")
            msg = ("No sales or purchase vouchers in that period.")
            self.result_label.setText(f"⚠ {msg}{company_hint}")
            self.result_label.setStyleSheet("color: #B07000;")
            return

        # Decide which entity to commit against.
        entity_id = self.entity_combo.currentData()
        if entity_id is None:
            # Auto-detect: match Tally's loaded company against the entity
            # master (canonical name or alias).
            if company_name:
                entity_id = _entity_id_for(company_name)
            if entity_id is None:
                QMessageBox.warning(
                    self, "No entity match",
                    f"Tally has '{company_name or '(unknown)'}' loaded, "
                    "which doesn't match any entity in Master Data. Pick a "
                    "target entity from the dropdown.")
                return
        else:
            # Operator picked an entity explicitly. If Tally's loaded
            # company doesn't match that entity, warn before committing —
            # this is the "wrong company in Tally" footgun.
            mapped_id = (_entity_id_for(company_name) if company_name
                         else None)
            if mapped_id is not None and mapped_id != entity_id:
                target_name = _entity_name(entity_id)
                resp = QMessageBox.question(
                    self, "Company mismatch",
                    f"Tally has <b>{company_name}</b> loaded, but you're "
                    f"importing into <b>{target_name}</b>.<br><br>"
                    f"The {len(result.vouchers)} voucher(s) Tally returned "
                    f"belong to {company_name}. Continue and commit them "
                    f"under {target_name}?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if resp != QMessageBox.Yes:
                    self.result_label.setText(
                        f"⚠ Cancelled — switch Tally to the right company "
                        f"and try again.")
                    self.result_label.setStyleSheet("color: #B07000;")
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
        # Always show which Tally company the data came from — eliminates
        # the "did I have the right one loaded?" guesswork.
        header_bits = [f"Pulled from <b>{company_name}</b>"
                       if company_name else "Pulled from Tally"]
        header_bits.append(f"{len(result.vouchers)} voucher(s) in range")
        lines.append(" — ".join(header_bits))
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
    alias table the operator uses for ledger names.

    Tries an exact match first, then a substring contains-match (Tally
    sometimes returns names like ``"Bilimoria Mehta & Co. - (From 1-Apr-...)"``
    with a split-period suffix — we want those to still hit Bilimoria).
    """
    from ..database import transaction
    key = (tally_company_name or "").strip().lower()
    if not key:
        return None
    with transaction() as conn:
        # Exact match first.
        row = conn.execute(
            "SELECT e.id FROM entities e "
            "LEFT JOIN entity_aliases a ON a.entity_id = e.id "
            "WHERE lower(e.name) = ? OR lower(a.alias) = ?",
            (key, key)).fetchone()
        if row:
            return row["id"]
        # Fall back to a contains-match (handles split-period suffixes).
        rows = conn.execute(
            "SELECT id, name FROM entities").fetchall()
        for r in rows:
            n = r["name"].strip().lower()
            if n and (n in key or key.startswith(n + " ")
                      or key.startswith(n + "-")):
                return r["id"]
    return None


def _entity_name(entity_id: int) -> str:
    """Human-readable name for an entity id (or ``'(unknown)'``)."""
    from ..database import transaction
    with transaction() as conn:
        row = conn.execute(
            "SELECT name FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
    return row["name"] if row else "(unknown)"
