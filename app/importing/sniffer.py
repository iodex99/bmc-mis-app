"""Auto-detect the layout of a Tally voucher-dump (sales/purchase) export.

Goal: every "actual" detailed Tally export — regardless of which entity it
came from or which exact column order Tally used — can be parsed without the
operator touching the column-mapping dialog. The sniffer scans the first
~30 rows for a Tally-style header row and returns a column map + format
hints. The header text varies a little across Tally versions and entities
(``Vch No.`` vs ``Voucher No.``, etc.) — the matcher is tolerant.
"""

from __future__ import annotations

import re
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

# Tally register banners. Each register carries the same ledger-line +
# cost-centre structure; what changes is the SIDE the revenue/expense
# sits on and whether the voucher adds to or subtracts from its kind.
#
# In this firm's workflow:
#   "Sales Register"           → sales       (revenue, +ve)
#   "Sales-D Register"         → sales       (Delhi branch sales)
#   "Sales-BR Register"        → sales       (Bangalore branch sales)
#   "Credit Note Register"     → sales       (sales returns, -ve)
#   "Credit Note-D Register"   → sales       (Delhi sales returns)
#   "Debit Note Register"      → sales       (SUPPLEMENTARY sales, +ve)
#   "Debit Note-D Register"    → sales       (Delhi supplementary sales)
#   "Other Income Register"    → sales       (other income, +ve)
#   "Purchase Register"        → purchase    (expense, +ve)
#   "Purchase-D Register"      → purchase
#
# Why Other Income routes to sales: Tally books "Other Income" vouchers
# (e.g. MF commission on the Qualzen entity) exactly like a sale — the
# party is debited and an income ledger credited, tagged to a partner
# cost centre. It's revenue, so it adds to that partner's income line.
#
# Why Debit Notes route to sales: in this firm's accounting practice,
# Debit Notes are issued BY the firm TO clients as supplementary
# invoices (additional billing on top of the original Sales invoice).
# They MUST add to the partner's revenue, not subtract from expenses.
# v0.3.55 had them on the purchase side (treated as purchase returns
# which is the textbook interpretation) — but that's wrong for this
# firm's books.
#
# Regex form so we tolerate any "-<branch>" suffix on the voucher type.
# ``sales?`` matches both "Sales" and the singular "Sale" some entities
# use — e.g. MASD Advisors exports a "New Sale Register" (voucher type
# "New Sale") for its foreign-currency invoices. ``other\s*income`` picks
# up the Qualzen "Other Income Register". Without these the banner went
# undetected, the file imported as kind=None and the operator got no
# auto-mapping ("system not picking up data").
_BANNER_SALES_RE = re.compile(
    r'\b(?:sales?|credit\s*note|debit\s*note|other\s*income)'
    r'(?:[\s-][\w-]*)?\s+register\b',
    re.IGNORECASE)
_BANNER_PURCHASE_RE = re.compile(
    r'\b(?:purchase)(?:[\s-][\w-]*)?\s+register\b',
    re.IGNORECASE)


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
    Matches any "<vch type> Register" line, including branch-suffixed
    variants like "Sales-D Register" or "Credit Note-D Register".
    """
    for row in grid[:10]:
        for cell in row:
            if cell is None:
                continue
            text = str(cell)
            if _BANNER_SALES_RE.search(text):
                return "sales"
            if _BANNER_PURCHASE_RE.search(text):
                return "purchase"
    return None


def detect_entity_name(grid: list[list[Any]]) -> str | None:
    """Pull the entity name from a Tally export's letterhead rows.

    Tally exports start with 4-6 banner rows giving the company name,
    address, then "<Type> Register" + a date range. The entity name is
    almost always the very first non-blank cell of row 0.

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
            if (_BANNER_SALES_RE.search(text)
                    or _BANNER_PURCHASE_RE.search(text)):
                return None
            if text[0].isdigit():
                continue
            return text
    return None


def detect_letterhead_text(grid: list[list[Any]]) -> str:
    """Join the company-name + address + contact rows into a single
    blob the entity matcher can search through.

    Important when two entities share the same company name but live at
    different addresses (e.g. Bilimoria Mumbai vs Bangalore). The
    matcher scans this text for distinguishing tokens like "Bengaluru"
    or "BMC Corporate" to disambiguate.
    """
    parts: list[str] = []
    for row in grid[:8]:
        for cell in row:
            if cell is None:
                continue
            text = str(cell).strip()
            if not text:
                continue
            # Banner row marks end of letterhead.
            if (_BANNER_SALES_RE.search(text)
                    or _BANNER_PURCHASE_RE.search(text)):
                return " \n ".join(parts)
            parts.append(text)
    return " \n ".join(parts)


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
    letterhead = detect_letterhead_text(grid)

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
            "letterhead_text": letterhead,
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
