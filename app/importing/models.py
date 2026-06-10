"""Dataclasses for records produced by the parsers (pre-database staging)."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field


@dataclass
class VoucherLine:
    """One ledger line inside a Tally voucher block.

    A real-world voucher splits into several lines — typically one revenue
    line ("Professional Fees") plus separate tax lines ("Output CGST 9%",
    "Output SGST 9%"). Each line can carry its own Cost Centre tag from
    Tally (the indented Dr/Cr sub-row); a multi-service voucher may have
    different partners attributed to different lines.
    """
    service: str = ""                    # ledger head text from Tally
    cost_centre: str | None = None       # raw CC string ("Mr. Vishal Kothari")
    amount: float = 0.0
    is_tax: bool = False                 # CGST / SGST / IGST / TDS / round-off


@dataclass
class ParsedVoucher:
    """One Tally voucher (sales or expense) extracted from a register."""
    date: _dt.date | None = None
    period: str | None = None
    vch_type: str = ""
    vch_no: str = ""
    party_name: str = ""
    kind: str = "expense"                 # sales | expense
    gross_amount: float = 0.0             # total billed / payable
    tax_amount: float = 0.0               # GST + TDS + round-off lines
    net_amount: float = 0.0               # taxable value -> the P&L figure
    ledger_heads: list[str] = field(default_factory=list)
    cc_allocations: list[tuple[str, float]] = field(default_factory=list)
    raw_cost_centre: str = ""             # dominant cost centre seen in Tally
    # Sales register only: one (service name, amount) pair per non-zero
    # service column in the row. When set, the importer creates one
    # voucher_split per entry instead of a single full-amount split.
    service_splits: list[tuple[str, float]] = field(default_factory=list)
    # Voucher-dump parser output: one VoucherLine per ledger row inside the
    # block, each carrying its own service + cost-centre + amount. When set,
    # commit produces one split per non-tax line; tax lines roll into
    # ``tax_amount``. Takes precedence over ``service_splits``.
    line_splits: list[VoucherLine] = field(default_factory=list)

    @property
    def description(self) -> str:
        return ", ".join(dict.fromkeys(self.ledger_heads))


@dataclass
class ParsedTimesheetRow:
    """One timesheet line: an employee's hours on a client for a day."""
    emp_code: str = ""
    emp_name: str = ""
    date: _dt.date | None = None
    period: str | None = None
    client_raw: str = ""
    task: str = ""
    hours: float = 0.0
    day_fraction: float = 0.0
    reporting_manager: str = ""
    description: str = ""
    is_billable: bool = True


@dataclass
class ParsedSalaryRow:
    """One salary-sheet line for an employee in a month."""
    period: str | None = None
    employee_name: str = ""
    raw_cost_centre: str = ""
    raw_entity: str = ""
    category: str = ""
    salary_paid: float = 0.0
    reimbursement: float = 0.0


@dataclass
class ParsedReimbursement:
    """One row of the dedicated reimbursement sheet.

    Distinct from ``ParsedSalaryRow.reimbursement`` (which holds the
    salary sheet's per-employee monthly total). Each row here ties an
    employee outlay to a specific client and records whether the
    client refunds the firm. Cost-centre attribution comes from the
    client master at MIS-build time.
    """
    period: str | None = None
    date: _dt.date | None = None
    employee_name: str = ""
    client_raw: str = ""
    amount: float = 0.0
    client_reimbursable: bool = False


@dataclass
class ParseResult:
    """Outcome of parsing one file."""
    file_type: str
    vouchers: list[ParsedVoucher] = field(default_factory=list)
    timesheet: list[ParsedTimesheetRow] = field(default_factory=list)
    salary: list[ParsedSalaryRow] = field(default_factory=list)
    reimbursements: list[ParsedReimbursement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return (len(self.vouchers) + len(self.timesheet)
                + len(self.salary) + len(self.reimbursements))
