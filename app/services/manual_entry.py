"""Manual single-row entry for vouchers, salary and reimbursements.

Lets the operator add one entry by hand instead of uploading a file — for
the "just one row" case. Everything lands in the SAME tables the importer
writes (``vouchers`` / ``voucher_splits``, ``salary_entries``,
``reimbursements``), so the MIS / dashboard pick it up with no special
handling. Each save is recorded under a dedicated "(manual entry)" import
batch per file type, so manual rows are still grouped and auditable.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from .. import config
from ..database import transaction
from ..importing.valueutils import period_of


# --- what the operator can book by hand --------------------------------------

@dataclass(frozen=True)
class VoucherType:
    """One entry in the Manual Entry page's "Type" dropdown.

    ``sign`` multiplies the entered amount (and its tax) before storage,
    so a Credit Note is stored NEGATIVE — the same shape the importer
    already gives an imported one (``parsers._vch_side_and_sign`` flips
    the ledger side and applies ``sign=-1``; ``tally_xml`` classifies it
    as a return). Carrying the direction in the amount rather than in a
    flag is what lets every SUMIFS in the MIS net a return off with no
    special case, so a hand-entered credit note behaves exactly like a
    pulled one.

    ``vch_type`` is the text written to ``vouchers.vch_type`` — the same
    wording Tally uses, so a manual credit note reads as "Credit Note"
    beside the imported ones. ``label`` is the dropdown text; ``noun`` is
    the short name buttons and confirmations use.
    """
    key: str
    label: str
    noun: str
    kind: str
    sign: int
    vch_type: str

    @property
    def is_expense(self) -> bool:
        return self.kind == config.VCH_EXPENSE

    @property
    def is_return(self) -> bool:
        """True when this type REDUCES the total it belongs to."""
        return self.sign < 0


#: Offered on the Manual Entry page, in display order. A Debit Note needs
#: no entry of its own — this firm books one as a supplementary sales
#: invoice (see ``parsers._vch_side_and_sign``), which is "Sales" here.
VOUCHER_TYPES = (
    VoucherType("sales", "Sales (revenue)", "sales voucher",
                config.VCH_SALES, +1, "Manual"),
    VoucherType("credit_note", "Credit Note (sales return)", "credit note",
                config.VCH_SALES, -1, "Credit Note"),
    VoucherType("expense", "Expense / Purchase", "expense voucher",
                config.VCH_EXPENSE, +1, "Manual"),
)

VOUCHER_TYPES_BY_KEY = {vt.key: vt for vt in VOUCHER_TYPES}


def voucher_type(key: str) -> VoucherType:
    """Look up a voucher type by key; an unknown key falls back to Sales."""
    return VOUCHER_TYPES_BY_KEY.get(key, VOUCHER_TYPES[0])


def _manual_batch(conn, file_type: str, entity_id: int | None,
                  period: str | None) -> int:
    """Reuse (or create) the manual-entry batch for this file type."""
    row = conn.execute(
        "SELECT id FROM import_batches "
        "WHERE file_type = ? AND file_name = '(manual entry)' "
        "AND ifnull(entity_id, 0) = ifnull(?, 0) "
        "AND ifnull(period, '') = ifnull(?, '') AND status = 'committed'",
        (file_type, entity_id, period)).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO import_batches (entity_id, file_type, file_name, period, "
        "status) VALUES (?, ?, '(manual entry)', ?, 'committed')",
        (entity_id, file_type, period)).lastrowid


def _auto_vch_no(conn, entity_id: int | None, kind: str) -> str:
    """A ``MAN-…`` voucher number no voucher of this kind already uses.

    The importer's dedup natural key is ``(entity, kind, vch_no)``, so a
    generated number has to be unique under it. A bare timestamp isn't
    enough now that Sales and Credit Notes share ``kind='sales'`` — two
    entries booked in the same second would collide — so a colliding
    stamp gets a counter suffix.
    """
    base = "MAN-" + _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    candidate, n = base, 1
    while conn.execute(
            "SELECT 1 FROM vouchers "
            "WHERE ifnull(entity_id, 0) = ifnull(?, 0) "
            "AND kind = ? AND vch_no = ?",
            (entity_id, kind, candidate)).fetchone():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def add_voucher(*, entity_id: int | None, txn_date, vtype: VoucherType,
                cost_centre_id: int | None, amount: float,
                vch_no: str = "", party_name: str = "",
                client_id: int | None = None, manager_id: int | None = None,
                service_id: int | None = None, expense_type: str | None = None,
                tax_amount: float = 0.0, description: str = "") -> int:
    """Add a one-line voucher (sales, credit note or expense) with one split.

    Mandatory: ``vtype``, ``cost_centre_id``, ``amount`` (and a date for
    the period). ``amount`` and ``tax_amount`` are given as POSITIVE
    magnitudes — how much is being billed or credited back — and the
    voucher type's ``sign`` decides the direction, so a Credit Note of
    10,000 stores −10,000 and nets off the partner's revenue. ``vch_no``
    is auto-generated when blank so the dedup natural key stays unique.
    ``net_amount`` = signed amount; gross = amount + tax, matching the
    Tally-pull convention that a return's gross is negative too.
    """
    period = period_of(txn_date)
    date_iso = txn_date.isoformat() if hasattr(txn_date, "isoformat") else \
        (str(txn_date) if txn_date else None)
    sign = vtype.sign
    amount = sign * abs(float(amount or 0.0))
    tax_amount = sign * abs(float(tax_amount or 0.0))
    with transaction() as conn:
        batch_id = _manual_batch(conn, vtype.kind, entity_id, period)
        if not (vch_no or "").strip():
            vch_no = _auto_vch_no(conn, entity_id, vtype.kind)
        vid = conn.execute(
            "INSERT INTO vouchers (batch_id, entity_id, txn_date, period, "
            "vch_type, vch_no, party_name, gross_amount, tax_amount, "
            "net_amount, description, raw_cost_centre, kind) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (batch_id, entity_id, date_iso, period, vtype.vch_type, vch_no,
             party_name or None, amount + tax_amount, tax_amount, amount,
             description or None, None, vtype.kind)).lastrowid
        conn.execute(
            "INSERT INTO voucher_splits (voucher_id, amount, cost_centre_id, "
            "manager_id, service_id, note) VALUES (?, ?, ?, ?, ?, ?)",
            (vid, amount, cost_centre_id, manager_id, service_id,
             expense_type or None))
        # Link the resolved client straight onto the voucher (manual entry
        # picks masters directly — no Review step needed).
        if client_id is not None:
            conn.execute("UPDATE vouchers SET client_id = ? WHERE id = ?",
                         (client_id, vid))
    return vid


def add_salary(*, period: str, employee_name: str,
               cost_centre_id: int | None, entity_id: int | None = None,
               category: str = "", salary_paid: float = 0.0,
               reimbursement: float = 0.0) -> int:
    """Add one salary row. Mandatory: ``period``, ``employee_name``,
    ``salary_paid`` (cost centre strongly recommended for attribution)."""
    with transaction() as conn:
        batch_id = _manual_batch(conn, "salary", entity_id, period)
        return conn.execute(
            "INSERT INTO salary_entries (batch_id, period, employee_name, "
            "cost_centre_id, entity_id, category, salary_paid, reimbursement) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (batch_id, period, employee_name, cost_centre_id, entity_id,
             category or None, float(salary_paid or 0.0),
             float(reimbursement or 0.0))).lastrowid


def add_reimbursement(*, period: str, employee_name: str, amount: float,
                      txn_date=None, client_id: int | None = None,
                      client_reimbursable: bool = False) -> int:
    """Add one reimbursement row. Mandatory: ``period``, ``employee_name``,
    ``amount``."""
    date_iso = txn_date.isoformat() if hasattr(txn_date, "isoformat") else \
        (str(txn_date) if txn_date else None)
    with transaction() as conn:
        batch_id = _manual_batch(conn, "reimbursement", None, period)
        return conn.execute(
            "INSERT INTO reimbursements (batch_id, period, txn_date, "
            "employee_name, client_id, amount, client_reimbursable) "
            "VALUES (?,?,?,?,?,?,?)",
            (batch_id, period, date_iso, employee_name, client_id,
             float(amount or 0.0), 1 if client_reimbursable else 0)).lastrowid
