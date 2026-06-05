"""Parse Tally's XML voucher dump into ``ParsedVoucher`` objects.

Tally Prime / ERP 9 exposes a Day Book report over HTTP+XML. The structure
is one ``<VOUCHER>`` per voucher, with multiple ``<ALLLEDGERENTRIES.LIST>``
children for each ledger line and one ``<COSTCENTREALLOCATIONS.LIST>``
under each ledger entry for the partner attribution. We re-use the same
``ParsedVoucher`` / ``VoucherLine`` dataclasses the Excel parser produces,
so commit / dedup / CC auto-match all operate identically downstream.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable
from xml.etree import ElementTree as ET

from .. import config
from .models import ParseResult, ParsedVoucher, VoucherLine
from .valueutils import is_tax_head, period_of


# Tally voucher-type → our ``kind``. Anything else is ignored (Payment,
# Receipt, Journal etc. don't belong in the partner P&L).
_KIND_MAP = {
    "sales": config.VCH_SALES,
    "purchase": config.VCH_EXPENSE,
}


def _norm_tag(tag: str) -> str:
    """Lower-case tag name, stripped of any XML namespace."""
    return tag.split("}", 1)[-1].lower()


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _find_first(elem: ET.Element, names: Iterable[str]) -> ET.Element | None:
    """Find the first direct child whose normalised tag is in *names*."""
    want = {n.lower() for n in names}
    for child in elem:
        if _norm_tag(child.tag) in want:
            return child
    return None


def _children_named(elem: ET.Element, names: Iterable[str]) -> list[ET.Element]:
    want = {n.lower() for n in names}
    return [c for c in elem if _norm_tag(c.tag) in want]


def _parse_tally_date(raw: str) -> _dt.date | None:
    """Tally dates are ``YYYYMMDD`` (e.g. ``20260401``)."""
    raw = raw.strip()
    if not raw:
        return None
    # 8-digit YYYYMMDD is by far the most common form.
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # Fallback: hyphenated / dotted forms used by some older Tally builds.
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> float:
    """Tally amounts come as plain decimals — negative means Debit."""
    raw = (raw or "").strip().replace(",", "").replace(" ", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _ledger_cost_centre(entry: ET.Element) -> str | None:
    """Walk into ``<CATEGORYALLOCATIONS.LIST><COSTCENTREALLOCATIONS.LIST>``
    and return the *first* cost-centre name found. We allocate the line's
    entire amount to that CC — Tally users typically attribute one ledger
    line to one partner. Multi-CC ledger entries fall through to the first.
    """
    for cat in _children_named(entry, ["categoryallocations.list"]):
        for cc in _children_named(cat, ["costcentreallocations.list"]):
            name = _text(_find_first(cc, ["name"]))
            if name:
                return name
    # Some Tally exports skip the category wrapper.
    for cc in _children_named(entry, ["costcentreallocations.list"]):
        name = _text(_find_first(cc, ["name"]))
        if name:
            return name
    return None


def _voucher_from_xml(velem: ET.Element) -> ParsedVoucher | None:
    """Convert a single ``<VOUCHER>`` element into a ParsedVoucher.

    Filters out anything that isn't a sales or purchase voucher. Optional
    sub-fields are read defensively — Tally Prime emits slightly different
    casing and includes some attributes ERP 9 omits.
    """
    vch_type_raw = (velem.get("VCHTYPE")
                    or _text(_find_first(velem, ["vouchertypename"])))
    kind = _KIND_MAP.get(vch_type_raw.strip().lower())
    if not kind:
        return None
    if (_text(_find_first(velem, ["iscancelled"])) or "").lower() == "yes":
        return None
    if (_text(_find_first(velem, ["isoptional"])) or "").lower() == "yes":
        return None

    date = _parse_tally_date(_text(_find_first(velem, ["date"])))
    vch_no = _text(_find_first(velem, ["vouchernumber"]))
    party = (_text(_find_first(velem, ["partyledgername"]))
             or _text(_find_first(velem, ["partyname"])))

    voucher = ParsedVoucher(
        date=date,
        period=period_of(date) if date else None,
        vch_type=vch_type_raw,
        vch_no=vch_no,
        party_name=party,
        kind=kind,
    )

    revenue_side_credit = (kind == config.VCH_SALES)
    for entry in _children_named(velem, ["allledgerentries.list",
                                          "ledgerentries.list"]):
        ledger = _text(_find_first(entry, ["ledgername"]))
        if not ledger:
            continue
        amount = _parse_amount(_text(_find_first(entry, ["amount"])))
        # Tally's AMOUNT sign: negative = Debit, positive = Credit.
        # For sales we want credit-side ledgers (revenue + GST), for
        # purchase debit-side (expense + input tax).
        is_credit = amount > 0
        if revenue_side_credit and not is_credit:
            # Debit-side party ledger on a sales voucher — skip; we already
            # store party_name on the voucher header.
            continue
        if (not revenue_side_credit) and is_credit:
            # Credit-side party ledger on a purchase voucher — skip.
            continue
        amt_abs = abs(amount)
        if amt_abs == 0:
            continue
        cc_name = _ledger_cost_centre(entry)
        voucher.line_splits.append(VoucherLine(
            service=ledger,
            cost_centre=cc_name,
            amount=amt_abs,
            is_tax=is_tax_head(ledger),
        ))

    if not voucher.line_splits:
        return None

    # Aggregate net + tax + raw_cost_centre (dominant). Mirrors the Excel
    # parser's final pass so the rest of the pipeline doesn't care which
    # source the voucher came from.
    voucher.gross_amount = sum(l.amount for l in voucher.line_splits)
    for line in voucher.line_splits:
        if line.is_tax:
            voucher.tax_amount += line.amount
        else:
            voucher.net_amount += line.amount
        if line.service and line.service not in voucher.ledger_heads:
            voucher.ledger_heads.append(line.service)
        if line.cost_centre:
            voucher.cc_allocations.append((line.cost_centre, line.amount))
    if voucher.cc_allocations:
        agg: dict[str, float] = {}
        for name, amt in voucher.cc_allocations:
            agg[name] = agg.get(name, 0.0) + amt
        voucher.raw_cost_centre = max(agg, key=lambda k: abs(agg[k]))

    return voucher


def parse_response(xml: bytes | str) -> ParseResult:
    """Parse a Tally Day-Book XML response into a ``ParseResult``.

    A single response can contain both sales and purchase vouchers — the
    file_type on the result reflects the dominant kind. Caller may want to
    split per kind before commit (we provide :func:`split_by_kind` for that).
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    # Tally uses Windows-1252 in some builds; lxml handles BOM/encoding via
    # the XML declaration header. ElementTree.fromstring works for both.
    root = ET.fromstring(xml)

    # Walk every <VOUCHER> element anywhere in the tree.
    vouchers: list[ParsedVoucher] = []
    for velem in root.iter():
        if _norm_tag(velem.tag) != "voucher":
            continue
        v = _voucher_from_xml(velem)
        if v is not None:
            vouchers.append(v)

    result = ParseResult(file_type=config.FILE_TYPE_SALES)
    result.vouchers = vouchers
    if not vouchers:
        result.warnings.append(
            "No sales or purchase vouchers in the Tally response for this "
            "period. Confirm Tally has the right company loaded and that "
            "the date range covers at least one voucher.")
    return result


def split_by_kind(result: ParseResult) -> dict[str, ParseResult]:
    """Split a mixed sales+purchase result into per-kind ParseResults.

    Keeps the original parser-emitted ``VoucherLine`` data intact; only
    the bucketing changes so commit can label each batch correctly.
    """
    buckets: dict[str, ParseResult] = {}
    for v in result.vouchers:
        ft = (config.FILE_TYPE_SALES if v.kind == config.VCH_SALES
              else config.FILE_TYPE_PURCHASE)
        r = buckets.setdefault(ft, ParseResult(file_type=ft))
        r.vouchers.append(v)
    return buckets
