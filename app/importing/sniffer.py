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

# Tally register banners. Credit/Debit Note Registers carry the same
# ledger-line + cost-centre structure as Sales/Purchase Registers; they
# just hold the return-side vouchers. For our schema both still book to
# the same side (returns are signed amounts on the parent kind):
#   "Sales Register"        → sales
#   "Credit Note Register"  → sales  (sales returns)
#   "Purchase Register"     → purchase
#   "Debit Note Register"   → purchase  (purchase returns)
_BANNER_SALES = ("sales register", "credit note register")
_BANNER_PURCHASE = ("purchase register", "debit note register")


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
    """Banner-row check for register type. Returns ``'sales'``,
    ``'purchase'``, or ``None`` if no Tally register banner is found.
    """
    for row in grid[:10]:
        for cell in row:
            t = _norm(cell)
            if any(b in t for b in _BANNER_SALES):
                return "sales"
            if any(b in t for b in _BANNER_PURCHASE):
                return "purchase"
    return None


def detect_entity_name(grid: list[list[Any]]) -> str | None:
    """Pull the entity name from a Tally export's letterhead rows.

    Tally exports start with 4-6 banner rows giving the company name,
    address, then "<Type> Register" + a date range. The entity name is
    almost always the very first non-blank cell of row 0. This returns
    the raw string (un-normalised) so the caller can run their own
    fuzzy match against the entities master.

    Stops scanning at the first row whose text looks like a register
    banner — past that we're into the table proper, not letterhead.
    """
    for row in grid[:8]:
        for cell in row:
            if cell is None:
                continue
            text = str(cell).strip()
            if not text:
                continue
            low = text.lower()
            # We've reached the register banner — past the letterhead.
            if any(b in low for b in (*_BANNER_SALES, *_BANNER_PURCHASE)):
                return None
            # Heuristic: skip rows that look like an address line (number-
            # heavy, contains comma) or a date range, prefer rows that
            # look like a company name (Title-case-ish, no leading digit).
            if text[0].isdigit():
                continue
            # Address lines almost always contain a comma; company names
            # rarely do (except for "& Co.").
            return text
    return None


def sniff(grid: list[list[Any]]) -> dict | None:
    """Sniff a Tally voucher-dump layout.

    Returns ``{header_row, colmap, kind, entity_name}`` or ``None`` if
    the file is not in a recognised voucher-dump format. ``kind`` is
    ``'sales'`` / ``'purchase'`` / ``None``; ``entity_name`` is the
    raw company name from the letterhead (or ``None``).
    """
    if not grid:
        return None
    kind = detect_kind(grid)
    entity_name = detect_entity_name(grid)

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
            "entity_name": entity_name,
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
