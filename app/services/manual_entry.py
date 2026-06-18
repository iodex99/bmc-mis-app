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

from ..database import transaction
from ..importing.valueutils import period_of


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


def add_voucher(*, entity_id: int | None, txn_date, kind: str,
                cost_centre_id: int | None, amount: float,
                vch_no: str = "", party_name: str = "",
                client_id: int | None = None, manager_id: int | None = None,
                service_id: int | None = None, expense_type: str | None = None,
                tax_amount: float = 0.0, description: str = "") -> int:
    """Add a one-line voucher (sales or expense) with a single split.

    Mandatory: ``kind``, ``cost_centre_id``, ``amount`` (and a date for the
    period). ``vch_no`` is auto-generated when blank so the dedup natural
    key stays unique. ``net_amount`` = ``amount``; gross = amount + tax.
    """
    period = period_of(txn_date)
    date_iso = txn_date.isoformat() if hasattr(txn_date, "isoformat") else \
        (str(txn_date) if txn_date else None)
    amount = float(amount or 0.0)
    tax_amount = float(tax_amount or 0.0)
    with transaction() as conn:
        batch_id = _manual_batch(conn, kind, entity_id, period)
        if not (vch_no or "").strip():
            stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
            vch_no = f"MAN-{stamp}"
        vid = conn.execute(
            "INSERT INTO vouchers (batch_id, entity_id, txn_date, period, "
            "vch_type, vch_no, party_name, gross_amount, tax_amount, "
            "net_amount, description, raw_cost_centre, kind) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (batch_id, entity_id, date_iso, period, "Manual", vch_no,
             party_name or None, amount + tax_amount, tax_amount, amount,
             description or None, None, kind)).lastrowid
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
