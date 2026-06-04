"""Auto-detect the layout of a Tally voucher-dump (sales/purchase) export.

Goal: every "actual" detailed Tally export — regardless of which entity it
came from or which exact column order Tally used — can be parsed without the
operator touching the column-mapping dialog. The sniffer scans the first
~30 rows for a Tally-style header row and returns a column map + format
hints. The header text varies a little across Tally versions and entities
(``Vch No.`` vs ``Voucher No.``, etc.) — the matcher is tolerant.
"""

from __future__ import annotations

from typing import Any

# Synonym sets for each canonical column. Compared after _norm() (lower-cased,
# stripped, trailing punctuation removed).
_DATE_SYNS = {"date"}
_PARTICULARS_SYNS = {"particulars"}
_VCH_NO_SYNS = {
    "vch no", "vch num", "voucher no", "voucher number", "vch", "vno",
}
_VCH_TYPE_SYNS = {"vch type", "voucher type"}
_DEBIT_SYNS = {"debit", "debit amount", "dr", "dr amount"}
_CREDIT_SYNS = {"credit", "credit amount", "cr", "cr amount"}

_BANNER_SALES = ("sales register",)
_BANNER_PURCHASE = ("purchase register",)


def _norm(value: Any) -> str:
    """Lower-case, strip, drop trailing punctuation. Empty for blanks."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text.rstrip(".:").strip() if text else ""


def _find_col(norms: list[str], synonyms: set[str]) -> int | None:
    for i, n in enumerate(norms):
        if n in synonyms:
            return i
    return None


def detect_kind(grid: list[list[Any]]) -> str | None:
    """Look at the banner rows for a 'Sales Register' / 'Purchase Register'
    marker. Returns ``'sales'``, ``'purchase'``, or ``None`` if neither.
    """
    for row in grid[:10]:
        for cell in row:
            t = _norm(cell)
            if any(b in t for b in _BANNER_SALES):
                return "sales"
            if any(b in t for b in _BANNER_PURCHASE):
                return "purchase"
    return None


def sniff(grid: list[list[Any]]) -> dict | None:
    """Sniff a Tally voucher-dump layout.

    Returns ``{header_row, colmap, kind}`` or ``None`` if the file does not
    look like a voucher-dump format. *colmap* uses canonical field names
    (``date``, ``particulars``, ``vch_no``, ``vch_type``, ``debit``,
    ``credit``). *kind* is ``'sales'`` / ``'purchase'`` / ``None``.
    """
    if not grid:
        return None
    kind = detect_kind(grid)

    for r_idx, row in enumerate(grid[:30]):
        norms = [_norm(c) for c in row]
        d_col = _find_col(norms, _DATE_SYNS)
        p_col = _find_col(norms, _PARTICULARS_SYNS)
        v_col = _find_col(norms, _VCH_NO_SYNS)
        if d_col is None or p_col is None or v_col is None:
            continue
        debit_col = _find_col(norms, _DEBIT_SYNS)
        credit_col = _find_col(norms, _CREDIT_SYNS)
        if debit_col is None or credit_col is None:
            continue
        return {
            "header_row": r_idx,
            "kind": kind,
            "colmap": {
                "date": d_col,
                "particulars": p_col,
                "vch_no": v_col,
                "vch_type": _find_col(norms, _VCH_TYPE_SYNS),
                "debit": debit_col,
                "credit": credit_col,
            },
        }
    return None
