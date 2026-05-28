"""Small utilities used across the app."""

from __future__ import annotations


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
