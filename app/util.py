"""Small utilities used across the app."""

from __future__ import annotations

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def month_label(period: str) -> str:
    """``'2026-04'`` → ``'Apr-26'`` — the reader-friendly period label used
    throughout the generated MIS (v0.3.100). Falls back to the raw value
    when it doesn't parse. IMPORTANT: several workbook SUMIFS/COUNTIFS
    match Period cells across sheets, so every sheet must render periods
    through this one function — mixing raw and pretty labels breaks them.
    """
    try:
        y, m = int(str(period)[:4]), int(str(period)[5:7])
        return f"{_MONTHS[m - 1]}-{y % 100:02d}"
    except (ValueError, IndexError, TypeError):
        return str(period or "")


def _next_period(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def periods_label(periods) -> str:
    """Human label for a period selection: one month → ``'Apr-26'``; a
    contiguous run → ``'Apr-25 to Jul-25'``; otherwise a comma list."""
    ps = sorted(p for p in (periods or []) if p)
    if not ps:
        return "—"
    if len(ps) == 1:
        return month_label(ps[0])
    try:
        contiguous = all(_next_period(ps[i]) == ps[i + 1]
                         for i in range(len(ps) - 1))
    except (ValueError, IndexError):
        contiguous = False
    if contiguous:
        return f"{month_label(ps[0])} to {month_label(ps[-1])}"
    return ", ".join(month_label(p) for p in ps)


def fmt_inr(value: float | int | None, decimals: int = 0) -> str:
    """Format a number using Indian comma grouping (e.g. ``12,34,56,789``).

    The last three digits are grouped together, then every two digits before
    that get their own comma — the standard lakh/crore convention.
    """
    if value is None or value == "":
        return ""
    n = float(value)
    negative = n < 0
    n = abs(n)
    if decimals:
        text = f"{n:.{decimals}f}"
        int_part, _, frac = text.partition(".")
    else:
        int_part = str(int(round(n)))
        frac = ""

    if len(int_part) > 3:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        int_part = ",".join(groups) + "," + last3

    result = int_part + (("." + frac) if frac else "")
    return ("-" + result) if negative else result
