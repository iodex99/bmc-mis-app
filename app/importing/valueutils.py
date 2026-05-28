"""Lenient converters for messy spreadsheet cell values."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from dateutil import parser as _dtparser

_TAX_KEYWORDS = (
    "cgst", "sgst", "igst", "gst ", "tcs", "tds", "round off", "roundoff",
)


def clean(value: Any) -> str:
    """Trim a cell to a clean string ('' for blanks)."""
    if value is None:
        return ""
    return str(value).strip()


def to_number(value: Any) -> float | None:
    """Parse a number from a cell; return None if not numeric."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[₹$]", "", text)
    if text in ("", "-"):
        return None
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        num = float(text)
    except ValueError:
        return None
    return -num if neg else num


def to_date(value: Any) -> _dt.date | None:
    """Parse a date from a cell (datetimes, Excel serials, or '1-Jan-26' text)."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, (int, float)) and 25000 < float(value) < 70000:
        # Excel date serial (covers ~1968-2091).
        try:
            return (_dt.datetime(1899, 12, 30)
                    + _dt.timedelta(days=float(value))).date()
        except (ValueError, OverflowError):
            pass
    try:
        return _dtparser.parse(str(value).strip(), dayfirst=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def period_of(value: Any) -> str | None:
    """Return the 'YYYY-MM' calendar-month bucket for a date-like cell."""
    d = to_date(value)
    return f"{d.year:04d}-{d.month:02d}" if d else None


def is_tax_head(particulars: str) -> bool:
    """True if a ledger head looks like a tax / round-off line, not a real expense."""
    low = particulars.lower()
    return any(k in low for k in _TAX_KEYWORDS)


def hours_from_duration(duration: Any, day_fraction: Any = None) -> float:
    """Convert a 'HH:MM' / numeric duration to hours.

    Falls back to ``day_fraction * 8`` when the duration cannot be read.
    """
    text = clean(duration)
    if ":" in text:
        parts = text.split(":")
        try:
            return int(parts[0]) + int(parts[1]) / 60.0
        except (ValueError, IndexError):
            pass
    num = to_number(duration)
    if num is not None:
        # A value <= 1 with no colon is most likely a day fraction.
        return num * 8.0 if num <= 1 and ":" not in text else num
    frac = to_number(day_fraction)
    return frac * 8.0 if frac is not None else 0.0
