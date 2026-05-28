"""Write a ParseResult into the database as a staged import batch.

Cost centres (a small fixed set) are resolved here. Clients and employees are
left unresolved — Phase 4 (Review & Map) handles those interactively.
"""

from __future__ import annotations

from collections import Counter

from ..database import transaction
from .models import ParseResult


def _dominant_period(result: ParseResult) -> str | None:
    counts: Counter[str] = Counter()
    for v in result.vouchers:
        if v.period:
            counts[v.period] += 1
    for t in result.timesheet:
        if t.period:
            counts[t.period] += 1
    for s in result.salary:
        if s.period:
            counts[s.period] += 1
    return counts.most_common(1)[0][0] if counts else None


def _cost_centre_id(conn, raw: str) -> int | None:
    if not raw:
        return None
    key = raw.strip().lower()
    row = conn.execute(
        "SELECT id FROM cost_centres WHERE lower(code) = ? OR lower(name) = ?",
        (key, key),
    ).fetchone()
    return row["id"] if row else None


def _entity_id(conn, raw: str) -> int | None:
    if not raw:
        return None
    key = raw.strip().lower()
    row = conn.execute(
        "SELECT e.id FROM entities e "
        "LEFT JOIN entity_aliases a ON a.entity_id = e.id "
        "WHERE lower(e.name) = ? OR lower(a.alias) = ?",
        (key, key),
    ).fetchone()
    return row["id"] if row else None


def existing_batch(entity_id: int | None, file_type: str,
                   period: str | None) -> dict | None:
    """Return a prior committed batch for the same entity/type/period, if any."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT id, file_name, imported_at FROM import_batches "
            "WHERE file_type = ? AND status = 'committed' "
            "AND ifnull(entity_id, 0) = ifnull(?, 0) AND ifnull(period, '') = ifnull(?, '')",
            (file_type, entity_id, period),
        ).fetchone()
    return dict(row) if row else None


def commit_result(result: ParseResult, entity_id: int | None,
                   file_name: str) -> int:
    """Persist *result* as a committed import batch; return the batch id."""
    period = _dominant_period(result)
    with transaction() as conn:
        batch_id = conn.execute(
            "INSERT INTO import_batches (entity_id, file_type, file_name, period, status) "
            "VALUES (?, ?, ?, ?, 'committed')",
            (entity_id, result.file_type, file_name, period),
        ).lastrowid

        for v in result.vouchers:
            cc_id = _cost_centre_id(conn, v.raw_cost_centre)
            vid = conn.execute(
                "INSERT INTO vouchers (batch_id, entity_id, txn_date, period, "
                "vch_type, vch_no, party_name, gross_amount, tax_amount, "
                "net_amount, description, ledger_head, raw_cost_centre, kind) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (batch_id, entity_id, v.date.isoformat() if v.date else None,
                 v.period, v.vch_type, v.vch_no, v.party_name, v.gross_amount,
                 v.tax_amount, v.net_amount, v.description,
                 "; ".join(v.ledger_heads), v.raw_cost_centre, v.kind),
            ).lastrowid
            # Default single split for the full net amount.
            conn.execute(
                "INSERT INTO voucher_splits (voucher_id, amount, cost_centre_id) "
                "VALUES (?, ?, ?)",
                (vid, v.net_amount, cc_id),
            )

        for t in result.timesheet:
            conn.execute(
                "INSERT INTO timesheet_entries (batch_id, emp_code, emp_name, "
                "txn_date, period, client_raw, task, hours, day_fraction, "
                "reporting_manager, description, is_billable) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (batch_id, t.emp_code, t.emp_name,
                 t.date.isoformat() if t.date else None, t.period, t.client_raw,
                 t.task, t.hours, t.day_fraction, t.reporting_manager,
                 t.description, 1 if t.is_billable else 0),
            )

        for s in result.salary:
            conn.execute(
                "INSERT INTO salary_entries (batch_id, period, employee_name, "
                "cost_centre_id, raw_cost_centre, entity_id, raw_entity, "
                "category, salary_paid, reimbursement) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (batch_id, s.period, s.employee_name,
                 _cost_centre_id(conn, s.raw_cost_centre), s.raw_cost_centre,
                 _entity_id(conn, s.raw_entity), s.raw_entity, s.category,
                 s.salary_paid, s.reimbursement),
            )
    return batch_id
