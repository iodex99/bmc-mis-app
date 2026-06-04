"""Write a ParseResult into the database as a staged import batch.

Cost centres (a small fixed set) are resolved here. Clients and employees are
left unresolved — Phase 4 (Review & Map) handles those interactively.

Dedup: vouchers carry a natural key of ``(entity_id, kind, vch_no)``. On
re-import, vouchers whose key already exists in the database are skipped;
the batch reports how many were new, identical-skip, and amount-mismatch.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..database import transaction
from .models import ParseResult, VoucherLine


@dataclass
class CommitReport:
    """Summary returned by :func:`commit_result`.

    The numbers come back to the import UI so the operator can see exactly
    what happened — particularly useful when a file is re-uploaded and the
    operator wants to know how many vouchers were skipped as duplicates.
    """
    batch_id: int
    new_vouchers: int = 0
    skipped_duplicates: int = 0          # same vch_no, same gross amount
    amount_mismatches: list[dict] = field(default_factory=list)  # diff amounts
    timesheet_rows: int = 0
    salary_rows: int = 0

    @property
    def total_inserted(self) -> int:
        return self.new_vouchers + self.timesheet_rows + self.salary_rows


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


def _ensure_service(conn, name: str) -> int | None:
    """Look up a service by name; create it if it doesn't exist."""
    name = name.strip()
    if not name:
        return None
    row = conn.execute(
        "SELECT id FROM services WHERE lower(name) = ?",
        (name.lower(),)).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO services(name) VALUES (?)", (name,)).lastrowid


def _cc_string_mapping(conn, raw: str) -> tuple[int | None, int | None]:
    """Look up a saved Cost Centre string → (cost_centre_id, manager_id)."""
    if not raw:
        return None, None
    row = conn.execute(
        "SELECT cost_centre_id, manager_id FROM cc_string_mappings "
        "WHERE lower(trim(raw_text)) = ?", (raw.strip().lower(),)).fetchone()
    if row:
        return row["cost_centre_id"], row["manager_id"]
    return None, None


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


_AMT_TOLERANCE = 1.0    # ₹ — rounding wiggle room when checking for duplicates


def _existing_voucher(conn, entity_id, kind, vch_no):
    """Return ``(id, gross_amount)`` of an existing voucher with the same
    natural key, or ``None``. The natural key is what the dedup pass uses to
    decide whether a re-import row is new, identical, or a conflict.
    """
    if not vch_no:
        return None
    row = conn.execute(
        "SELECT id, gross_amount FROM vouchers "
        "WHERE ifnull(entity_id, 0) = ifnull(?, 0) "
        "  AND kind = ? AND vch_no = ?",
        (entity_id, kind, vch_no),
    ).fetchone()
    return (row["id"], row["gross_amount"]) if row else None


def commit_result(result: ParseResult, entity_id: int | None,
                   file_name: str) -> CommitReport:
    """Persist *result* as a committed import batch.

    Returns a :class:`CommitReport` summarising what was inserted, skipped
    as duplicate, or flagged as an amount mismatch. The batch row is
    always created (even if every voucher was skipped) so the operator can
    see the upload happened.
    """
    period = _dominant_period(result)
    report = CommitReport(batch_id=0)
    with transaction() as conn:
        batch_id = conn.execute(
            "INSERT INTO import_batches (entity_id, file_type, file_name, period, status) "
            "VALUES (?, ?, ?, ?, 'committed')",
            (entity_id, result.file_type, file_name, period),
        ).lastrowid
        report.batch_id = batch_id

        for v in result.vouchers:
            existing = _existing_voucher(conn, entity_id, v.kind, v.vch_no)
            if existing is not None:
                ex_id, ex_gross = existing
                if abs((ex_gross or 0) - (v.gross_amount or 0)) <= _AMT_TOLERANCE:
                    report.skipped_duplicates += 1
                else:
                    report.amount_mismatches.append({
                        "vch_no": v.vch_no,
                        "existing_gross": ex_gross,
                        "new_gross": v.gross_amount,
                        "existing_voucher_id": ex_id,
                    })
                continue

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
            report.new_vouchers += 1

            if v.line_splits:
                # Voucher-dump parser: one split per non-tax ledger line, each
                # with its own service + raw cost-centre string. Tax lines
                # stay aggregated in voucher.tax_amount (handled in parser).
                for line in v.line_splits:
                    if line.is_tax:
                        continue
                    svc_id = _ensure_service(conn, line.service)
                    raw_cc = line.cost_centre or v.raw_cost_centre
                    line_cc_id = _cost_centre_id(conn, raw_cc) if raw_cc else None
                    conn.execute(
                        "INSERT INTO voucher_splits "
                        "(voucher_id, amount, cost_centre_id, service_id, "
                        " raw_cost_centre) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (vid, line.amount, line_cc_id, svc_id, raw_cc),
                    )
            elif v.service_splits:
                # Legacy wide-flat sales parser: one split per service column,
                # voucher-level cost centre on each.
                for svc_name, amount in v.service_splits:
                    svc_id = _ensure_service(conn, svc_name)
                    conn.execute(
                        "INSERT INTO voucher_splits "
                        "(voucher_id, amount, cost_centre_id, service_id, "
                        " raw_cost_centre) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (vid, amount, cc_id, svc_id, v.raw_cost_centre),
                    )
            else:
                conn.execute(
                    "INSERT INTO voucher_splits "
                    "(voucher_id, amount, cost_centre_id, raw_cost_centre) "
                    "VALUES (?, ?, ?, ?)",
                    (vid, v.net_amount, cc_id, v.raw_cost_centre),
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
            report.timesheet_rows += 1

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
            report.salary_rows += 1
    # Auto-mapping after every import:
    #   • apply saved cc-string → (partner, manager) mappings to the new
    #     voucher splits
    #   • smart fuzzy-match any *new* unmapped cc strings to partners /
    #     managers (handles "Mr. Shreyans Dedhia" → SD, "Prashant - Shreyans"
    #     → SD+Prashant, etc.) — the bulk of cc strings get auto-resolved
    #     on first import
    #   • apply saved client aliases so vouchers / timesheet rows get linked
    #   • run all inference passes — cost centres get propagated from the
    #     Sales Register into clients, from the salary sheet into employees,
    #     from the timesheet into employee→manager, and from employees up to
    #     their managers' cost centres.
    from ..services.resolution import (
        apply_known_cc_string_mappings,
        apply_known_client_aliases,
        auto_match_cc_strings,
        infer_all_masters,
    )
    apply_known_cc_string_mappings()
    auto_match_cc_strings()
    apply_known_client_aliases()
    infer_all_masters()
    return report
