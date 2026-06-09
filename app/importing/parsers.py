"""Parsers that turn a raw spreadsheet grid + column map into staged records.

A *column map* is ``{canonical_field: column_index}``. *data_start* is the first
row index holding real data (just after the header row).
"""

from __future__ import annotations

from typing import Any

from .. import config
from .models import (
    ParsedSalaryRow,
    ParsedTimesheetRow,
    ParsedVoucher,
    ParseResult,
    VoucherLine,
)
from .valueutils import (
    clean,
    hours_from_duration,
    is_tax_head,
    mis_period_for_timesheet_date,
    period_of,
    to_date,
    to_number,
)

ColMap = dict[str, int]


def _cell(row: list[Any], idx: int | None) -> Any:
    if idx is None or idx < 0 or idx >= len(row):
        return None
    return row[idx]


def _is_blank(row: list[Any]) -> bool:
    return all(c in (None, "") for c in row)


def _marker(row: list[Any]) -> bool:
    """True if the row carries a 'Dr'/'Cr' cost-centre allocation marker."""
    return any(clean(c).lower() in ("dr", "cr") for c in row)


def _first_number(row: list[Any]) -> float | None:
    for c in row:
        n = to_number(c)
        if n is not None:
            return n
    return None


# --- Tally sales / purchase register ----------------------------------------

def _marker_side(row: list[Any]) -> str | None:
    """Return ``'dr'``, ``'cr'`` or ``None`` for a Dr/Cr cost-centre sub-row."""
    for cell in row:
        t = clean(cell).lower()
        if t == "dr":
            return "dr"
        if t == "cr":
            return "cr"
    return None


def _vch_side_and_sign(vch_type: str, file_kind: str) -> tuple[str, int]:
    """Return ``(side, sign)`` for the current voucher.

    * ``side`` — which column the ledger lines AND their CC tags live in
      (``'cr'`` = Credit column, ``'dr'`` = Debit column).
    * ``sign`` — multiplier applied to the parsed amount before storage.

    In a Sales Register, ordinary Sales vouchers have ledger lines on the
    Credit side (revenue is credited). A Credit Note voucher is a sales
    return — Tally inverts the sides: ledger lines move to Debit, CC tags
    say "Dr". The parser flips side + applies sign=-1 so returns reduce
    revenue.

    Debit Notes are this firm's "supplementary sales" mechanism: an
    additional bill raised on top of the original Sales invoice. Tally
    books them with the customer DEBITED (party col) and revenue
    CREDITED — structurally identical to a regular Sales voucher.
    So Debit Note → ``('cr', +1)``, treating it as an addition to the
    partner's revenue.
    """
    t = (vch_type or "").strip().lower()
    # Credit Note (sales return) — lines on Debit, sign -1.
    if t.startswith("credit note"):
        return "dr", -1
    # Debit Note (supplementary sales invoice in this firm's books) —
    # lines on Credit (same as Sales), sign +1 (ADDS to revenue).
    if t.startswith("debit note"):
        return "cr", +1
    # Defaults follow the file kind.
    if file_kind == config.VCH_SALES:
        return "cr", +1
    return "dr", +1


def parse_tally(grid: list[list[Any]], colmap: ColMap, data_start: int,
                kind: str) -> ParseResult:
    """Parse a Tally voucher-dump register into vouchers with per-line splits.

    Layout: a row carrying a date starts a new voucher; following sub-rows are
    either ledger lines (service name + amount on Debit/Credit) or indented
    Dr/Cr cost-centre tags. Each ledger line is followed by zero or more
    matching-side Dr/Cr sub-rows naming the cost centre(s) the amount is
    attributed to. Tax / GST / round-off lines are detected by keyword and
    aggregated into the voucher's ``tax_amount`` rather than becoming splits.

    The same parser handles every register variant — Sales, Sales-D
    (Delhi suffix), Credit Note, Credit Note-D, Purchase, Debit Note —
    by picking the right side + sign **per voucher** (not per file).
    A Sales Register can legitimately include Credit Note vouchers, and
    those need the side flipped (lines on Debit instead of Credit) with
    sign=-1 (returns reduce the partner's net revenue).
    """
    result = ParseResult(file_type=kind)
    d_i = colmap.get("date")
    p_i = colmap.get("particulars")
    vt_i = colmap.get("vch_type")
    vn_i = colmap.get("vch_no")
    dr_i = colmap.get("debit")
    cr_i = colmap.get("credit")

    # File-level default (used until the first voucher header arrives).
    cur_side = "cr" if kind == config.VCH_SALES else "dr"
    cur_col = cr_i if kind == config.VCH_SALES else dr_i
    cur_sign = 1

    current: ParsedVoucher | None = None
    pending_line: VoucherLine | None = None

    def flush_pending():
        """Commit the in-flight ledger line to the current voucher."""
        nonlocal pending_line
        if current is not None and pending_line is not None:
            current.line_splits.append(pending_line)
        pending_line = None

    for row in grid[data_start:]:
        if _is_blank(row):
            continue
        date = to_date(_cell(row, d_i))

        if date is not None:                       # ---- voucher header ----
            flush_pending()
            credit = to_number(_cell(row, cr_i)) or 0.0
            debit = to_number(_cell(row, dr_i)) or 0.0
            # For sales/purchase the customer/vendor is debited/credited
            # respectively — that's the "gross". For credit/debit notes the
            # opposite side carries it.
            vch_type = clean(_cell(row, vt_i))
            cur_side, cur_sign = _vch_side_and_sign(vch_type, kind)
            cur_col = cr_i if cur_side == "cr" else dr_i
            party_col = dr_i if cur_side == "cr" else cr_i
            gross = to_number(_cell(row, party_col)) or 0.0
            if gross == 0:
                gross = max(credit, debit)
            current = ParsedVoucher(
                date=date,
                period=period_of(date),
                vch_type=vch_type,
                vch_no=clean(_cell(row, vn_i)),
                party_name=clean(_cell(row, p_i)),
                kind=kind,
                gross_amount=gross,
            )
            result.vouchers.append(current)
            continue

        if current is None:
            continue

        side = _marker_side(row)
        if side is not None:
            # Indented Dr/Cr cost-centre tag. Attribute only when the
            # marker matches the current voucher's ledger-line side.
            if side == cur_side and pending_line is not None:
                pending_line.cost_centre = clean(_cell(row, p_i)) or None
                tag_amt = _first_number(row)
                if tag_amt is not None and pending_line.amount == 0:
                    pending_line.amount = float(tag_amt) * cur_sign
                flush_pending()
            continue

        # Plain ledger line (no Dr/Cr marker).
        head = clean(_cell(row, p_i))
        if not head:
            continue
        amt = to_number(_cell(row, cur_col))
        if amt is None or amt == 0:
            continue

        flush_pending()
        pending_line = VoucherLine(
            service=head,
            amount=float(amt) * cur_sign,
            is_tax=is_tax_head(head),
        )

    flush_pending()

    # Aggregate net / tax + pick the dominant non-tax CC for backward compat.
    for v in result.vouchers:
        for line in v.line_splits:
            if line.is_tax:
                v.tax_amount += line.amount
            else:
                v.net_amount += line.amount
            if line.service and line.service not in v.ledger_heads:
                v.ledger_heads.append(line.service)
            if line.cost_centre:
                v.cc_allocations.append((line.cost_centre, line.amount))
        if v.cc_allocations:
            agg: dict[str, float] = {}
            for name, amt in v.cc_allocations:
                agg[name] = agg.get(name, 0.0) + amt
            v.raw_cost_centre = max(agg, key=lambda k: abs(agg[k]))

    if not result.vouchers:
        result.warnings.append("No vouchers were detected — check the column map.")
    return result


# --- Timesheet ---------------------------------------------------------------

def parse_timesheet(grid: list[list[Any]], colmap: ColMap,
                    data_start: int) -> ParseResult:
    """Parse a flat timesheet into per-employee/client/day rows."""
    result = ParseResult(file_type=config.FILE_TYPE_TIMESHEET)
    for row in grid[data_start:]:
        if _is_blank(row):
            continue
        name = clean(_cell(row, colmap.get("emp_name")))
        client = clean(_cell(row, colmap.get("client")))
        date = to_date(_cell(row, colmap.get("date")))
        if not name or not client:
            continue
        hours = hours_from_duration(
            _cell(row, colmap.get("duration")),
            _cell(row, colmap.get("day_fraction")),
        )
        result.timesheet.append(ParsedTimesheetRow(
            emp_code=clean(_cell(row, colmap.get("emp_code"))),
            emp_name=name,
            date=date,
            # Timesheet uses the firm's 21st→20th cycle: day ≤ 20 is the
            # current MIS month, day ≥ 21 rolls into next month's MIS.
            period=mis_period_for_timesheet_date(date),
            client_raw=client,
            task=clean(_cell(row, colmap.get("task"))),
            hours=hours,
            day_fraction=to_number(_cell(row, colmap.get("day_fraction"))) or 0.0,
            reporting_manager=clean(_cell(row, colmap.get("reporting_manager"))),
            description=clean(_cell(row, colmap.get("description"))),
            is_billable="non billable" not in client.lower(),
        ))
    if not result.timesheet:
        result.warnings.append("No timesheet rows were detected — check the column map.")
    return result


# --- Salary & reimbursements -------------------------------------------------

def parse_salary(grid: list[list[Any]], colmap: ColMap,
                 data_start: int) -> ParseResult:
    """Parse a flat salary & reimbursements sheet."""
    result = ParseResult(file_type=config.FILE_TYPE_SALARY)
    for row in grid[data_start:]:
        if _is_blank(row):
            continue
        name = clean(_cell(row, colmap.get("name")))
        if not name:
            continue
        result.salary.append(ParsedSalaryRow(
            period=period_of(_cell(row, colmap.get("month"))),
            employee_name=name,
            raw_cost_centre=clean(_cell(row, colmap.get("cost_centre"))),
            raw_entity=clean(_cell(row, colmap.get("entity"))),
            category=clean(_cell(row, colmap.get("category"))),
            salary_paid=to_number(_cell(row, colmap.get("salary_paid"))) or 0.0,
            reimbursement=to_number(_cell(row, colmap.get("reimbursement"))) or 0.0,
        ))
    if not result.salary:
        result.warnings.append("No salary rows were detected — check the column map.")
    return result


_CANCELLED_KEYWORDS = ("cancel", "void", "cancelled", "voided")


def parse_sales_flat(grid: list[list[Any]], colmap: ColMap, data_start: int,
                     service_map: dict[int, str],
                     tax_cols: list[int]) -> ParseResult:
    """Parse a flat sales register (one row per invoice).

    *service_map* maps column index → service name; each non-zero amount in a
    service column becomes one split. *tax_cols* lists indices summed into
    ``tax_amount``. Rows whose cost-centre string looks like "(cancelled)" are
    skipped.
    """
    result = ParseResult(file_type=config.FILE_TYPE_SALES)
    d_i = colmap.get("date")
    p_i = colmap.get("particulars")
    cc_i = colmap.get("cost_centre_string")
    vt_i = colmap.get("vch_type")
    vn_i = colmap.get("vch_no")

    for row in grid[data_start:]:
        if _is_blank(row):
            continue
        date = to_date(_cell(row, d_i))
        if date is None:
            continue
        cc_str = clean(_cell(row, cc_i))
        if not cc_str:
            continue
        low = cc_str.lower()
        if any(k in low for k in _CANCELLED_KEYWORDS):
            continue                                  # skip cancelled invoices

        splits: list[tuple[str, float]] = []
        for col_idx, svc_name in service_map.items():
            amt = to_number(_cell(row, col_idx))
            if amt is not None and abs(amt) > 0.005:
                splits.append((svc_name, float(amt)))
        if not splits:
            continue                                  # nothing billable

        tax_total = 0.0
        for ci in tax_cols:
            v = to_number(_cell(row, ci))
            if v is not None:
                tax_total += float(v)

        net = sum(a for _s, a in splits)
        voucher = ParsedVoucher(
            date=date, period=period_of(date),
            vch_type=clean(_cell(row, vt_i)),
            vch_no=clean(_cell(row, vn_i)),
            party_name=clean(_cell(row, p_i)),
            kind=config.VCH_SALES,
            gross_amount=net + tax_total,
            tax_amount=tax_total,
            net_amount=net,
            raw_cost_centre=cc_str,
            ledger_heads=[s for s, _a in splits],
            service_splits=splits,
        )
        result.vouchers.append(voucher)

    if not result.vouchers:
        result.warnings.append("No sales rows parsed — check the column map.")
    return result


def parse(file_type: str, grid: list[list[Any]], colmap: ColMap,
          data_start: int, **extras) -> ParseResult:
    """Dispatch to the right parser for *file_type*.

    Sales has two valid layouts: the Tally voucher-dump (multi-row blocks
    with per-line cost-centre tags — preferred) and the legacy wide flat
    format (one row per invoice, columns per service). We pick by what the
    column map looks like:

    * ``debit`` + ``credit`` in *colmap* → voucher-dump → :func:`parse_tally`
    * ``service_map`` provided in *extras* → legacy wide → :func:`parse_sales_flat`
    """
    if file_type == config.FILE_TYPE_PURCHASE:
        return parse_tally(grid, colmap, data_start, config.VCH_EXPENSE)
    if file_type == config.FILE_TYPE_SALES:
        service_map = extras.get("service_map") or {}
        if "debit" in colmap and "credit" in colmap and not service_map:
            return parse_tally(grid, colmap, data_start, config.VCH_SALES)
        return parse_sales_flat(
            grid, colmap, data_start, service_map,
            extras.get("tax_cols", []))
    if file_type == config.FILE_TYPE_TIMESHEET:
        return parse_timesheet(grid, colmap, data_start)
    if file_type == config.FILE_TYPE_SALARY:
        return parse_salary(grid, colmap, data_start)
    raise ValueError(f"Unknown file type: {file_type}")
