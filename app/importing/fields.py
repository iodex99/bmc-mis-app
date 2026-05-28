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


# Tally sales & purchase registers share the same voucher structure.
_TALLY_FIELDS = [
    F("date", "Date", required=True),
    F("particulars", "Particulars", required=True),
    F("vch_type", "Voucher Type"),
    F("vch_no", "Voucher No."),
    F("debit", "Debit", required=True),
    F("credit", "Credit", required=True),
    F("taxable_amount", "Taxable Amount"),
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

FIELDS: dict[str, list[F]] = {
    config.FILE_TYPE_SALES: _TALLY_FIELDS,
    config.FILE_TYPE_PURCHASE: _TALLY_FIELDS,
    config.FILE_TYPE_TIMESHEET: _TIMESHEET_FIELDS,
    config.FILE_TYPE_SALARY: _SALARY_FIELDS,
}


def fields_for(file_type: str) -> list[F]:
    return FIELDS[file_type]
