"""Canonical fields each file type must be mapped to.

The column-template UI shows these; the operator maps each to a spreadsheet
column once per new layout, and the mapping is remembered.
"""

from __future__ import annotations

from .. import config


class F:
    """One canonical field: key, human label, required flag."""

    def __init__(self, key: str, label: str, required: bool = False) -> None:
        self.key = key
        self.label = label
        self.required = required


# Tally Purchase Register — multi-row voucher blocks.
_PURCHASE_FIELDS = [
    F("date", "Date", required=True),
    F("particulars", "Particulars", required=True),
    F("vch_type", "Voucher Type"),
    F("vch_no", "Voucher No."),
    F("debit", "Debit", required=True),
    F("credit", "Credit", required=True),
    F("taxable_amount", "Taxable Amount"),
]

# Tally Sales Register — flat one-row-per-invoice layout. Service revenue is
# spread across many columns (one per service) and the Tally "Cost Center"
# column carries a "Partner – Manager" identifier string. Both are configured
# in the per-column role section of the mapping dialog, not as canonical
# fields here.
_SALES_FIELDS = [
    F("date", "Date", required=True),
    F("particulars", "Particulars (client)", required=True),
    F("cost_centre_string", "Cost Centre (Tally column)", required=True),
    F("vch_type", "Voucher Type"),
    F("vch_no", "Voucher No."),
    F("gross_total", "Gross Total (cross-check)"),
]

_TIMESHEET_FIELDS = [
    F("emp_code", "Employee Code"),
    F("emp_name", "Employee Name", required=True),
    F("date", "Date", required=True),
    F("client", "Client Name", required=True),
    F("task", "Task"),
    F("duration", "Duration / Hours", required=True),
    F("day_fraction", "Day Fraction"),
    F("description", "Description"),
    F("reporting_manager", "Reporting Manager"),
]

_SALARY_FIELDS = [
    F("month", "Month", required=True),
    F("name", "Employee Name", required=True),
    F("cost_centre", "Cost Centre", required=True),
    F("entity", "Entity"),
    F("category", "Category (E/CA/CMA)"),
    F("salary_paid", "Salary Paid", required=True),
    F("reimbursement", "Reimbursement"),
]

# Per-row employee reimbursement sheet. Distinct from the per-employee
# aggregate ``reimbursement`` column on the salary sheet.
_REIMBURSEMENT_FIELDS = [
    F("period", "Period", required=True),
    F("date", "Date"),
    F("name", "Employee Name", required=True),
    F("amount", "Reimbursement Amount", required=True),
    F("client", "Client Name", required=True),
    F("client_reimbursable", "Client Reimbursement (Yes/No)", required=True),
]

FIELDS: dict[str, list[F]] = {
    config.FILE_TYPE_SALES: _SALES_FIELDS,
    config.FILE_TYPE_PURCHASE: _PURCHASE_FIELDS,
    config.FILE_TYPE_TIMESHEET: _TIMESHEET_FIELDS,
    config.FILE_TYPE_SALARY: _SALARY_FIELDS,
    config.FILE_TYPE_REIMBURSEMENT: _REIMBURSEMENT_FIELDS,
}


def fields_for(file_type: str) -> list[F]:
    return FIELDS[file_type]
