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


# XML 1.0 forbids most ASCII control characters. Tally sometimes emits them
# *both* as raw bytes (inside ledger names / descriptions) and as numeric
# character references (``&#0;``, ``&#11;`` etc.) — Python's expat parser
# rejects both with "reference to invalid character number". We strip them
# before parsing. Tab (\t), LF (\n) and CR (\r) are preserved.
_RAW_BAD_BYTES = re.compile(rb"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_BAD_DEC_REF = re.compile(
    rb"&#(?:0*[0-8]|0*1[12]|0*1[4-9]|0*2[0-9]|0*3[01]);")
_BAD_HEX_REF = re.compile(
    rb"&#x0*(?:[0-8bBcCeEfF]|1[0-9a-fA-F]);")

# Tally Prime sometimes emits namespaced tags (``<udf:UserField>``,
# ``<urn:Foo>``) without declaring the namespace, which expat rejects as
# "unbound prefix". We don't read any namespaced fields, so the safest
# fix is to strip namespace declarations + prefixes before parsing.
_NS_DECL = re.compile(rb'\s+xmlns(?::[\w.-]+)?\s*=\s*"[^"]*"')
_NS_DECL_SQ = re.compile(rb"\s+xmlns(?::[\w.-]+)?\s*=\s*'[^']*'")
_NS_TAG = re.compile(rb"(</?)([A-Za-z_][\w.-]*):([A-Za-z_])")
_NS_ATTR = re.compile(rb'(\s)([A-Za-z_][\w.-]*):([A-Za-z_][\w.-]*\s*=)')

# Bare ``&`` (not part of a valid entity) crashes expat too — Tally
# occasionally writes "M&S Co" without escaping it.
_BARE_AMP = re.compile(rb"&(?!(?:#\d+|#x[0-9a-fA-F]+|amp|lt|gt|quot|apos);)")


def _sanitize_xml_bytes(data: bytes) -> bytes:
    """Strip the patterns of malformed XML that Tally is known to emit.

    Handled (each documented in the regex blocks above):

    * raw ASCII control bytes
    * numeric character references to those same chars
    * undeclared namespace prefixes (``udf:``, ``urn:`` etc.)
    * bare ``&`` not starting a valid entity
    * UTF-8 BOM at the start of the payload
    """
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = _RAW_BAD_BYTES.sub(b"", data)
    data = _BAD_DEC_REF.sub(b"", data)
    data = _BAD_HEX_REF.sub(b"", data)
    # Order matters here: drop xmlns declarations first, then drop the
    # prefixes from tags + attributes (otherwise an unconverted prefix
    # could re-introduce a parse error if its declaration was stripped).
    data = _NS_DECL.sub(b"", data)
    data = _NS_DECL_SQ.sub(b"", data)
    data = _NS_TAG.sub(rb"\1\3", data)
    data = _NS_ATTR.sub(rb"\1\3", data)
    data = _BARE_AMP.sub(b"&amp;", data)
    return data


def _parse_xml(data: bytes) -> ET.Element:
    """Parse Tally XML, recovering from encoding + malformed-payload issues.

    Order: sanitize -> try UTF-8 -> fall back to cp1252 (the default
    Windows codepage Tally ERP 9 ships in non-Unicode mode). Raises
    ``ET.ParseError`` only if every recovery path fails.
    """
    cleaned = _sanitize_xml_bytes(data)
    try:
        return ET.fromstring(cleaned)
    except ET.ParseError:
        pass
    # cp1252-encoded payload mislabelled as UTF-8 — re-decode and retry.
    try:
        text = cleaned.decode("cp1252", errors="replace")
    except Exception:                                # noqa: BLE001
        text = cleaned.decode("utf-8", errors="replace")
    # Drop any encoding="…" declaration so ET trusts the now-Unicode text.
    text = re.sub(r'<\?xml[^?]*\?>', "", text, count=1)
    return ET.fromstring(text)


# Tally voucher-type → our ``kind``. Anything else is ignored (Payment,
# Receipt, Journal etc. don't belong in the partner P&L). Operators
# routinely create custom variants ("Sales - Delhi", "Sales - Export",
# "Purchase Imports", "Sales Mumbai", etc.) — all of these should map to
# the same underlying kind, so we prefix-match instead of equality-match.

# Voucher type matchers. Each is a prefix regex that allows space / hyphen
# / slash / dot / end-of-string after (and between) trigger words, so
# operator-customised variants like "Sales - Delhi", "Credit Note D",
# "Debit-Note", "Purchase Imports" all land on the right classification.
# The "next-char" group ``(?:[\s\-/.]|$)`` keeps "Credit Notebook" or
# "Salesperson" from accidentally matching.
_SEP = r'[\s\-/.]'
_VCH_PREFIX_SALES = re.compile(rf'^sales(?:{_SEP}|$)', re.IGNORECASE)
_VCH_PREFIX_PURCHASE = re.compile(rf'^purchase(?:{_SEP}|$)', re.IGNORECASE)
_VCH_PREFIX_CREDIT_NOTE = re.compile(
    rf'^credit{_SEP}*note(?:{_SEP}|$)', re.IGNORECASE)
_VCH_PREFIX_DEBIT_NOTE = re.compile(
    rf'^debit{_SEP}*note(?:{_SEP}|$)', re.IGNORECASE)
_VCH_PREFIX_SALES_RETURN = re.compile(
    rf'^sales{_SEP}*return(?:{_SEP}|$)', re.IGNORECASE)
_VCH_PREFIX_PURCHASE_RETURN = re.compile(
    rf'^purchase{_SEP}*return(?:{_SEP}|$)', re.IGNORECASE)


def _classify_vch_type(raw: str) -> tuple[str, bool] | None:
    """Return ``(kind, is_return)`` for a Tally VoucherTypeName.

    *is_return* flags credit notes / debit notes / sales returns /
    purchase returns — entries that **reduce** the running revenue
    or expense rather than adding to it.

    Matches the trigger word as a prefix followed by a space, hyphen,
    slash or end-of-string, so all operator-customised variants land
    on the right classification:

    * ``Sales``, ``Sales - Delhi``, ``Sales/BLR``, ``Sales Mumbai``
      → ``(VCH_SALES, False)``
    * ``Credit Note``, ``Credit Note D``, ``Credit Note - Delhi``,
      ``Sales Return`` → ``(VCH_SALES, True)`` (negative amounts)
    * ``Purchase``, ``Purchase Imports`` → ``(VCH_EXPENSE, False)``
    * ``Debit Note``, ``Debit Note D``, ``Purchase Return``
      → ``(VCH_EXPENSE, True)`` (negative amounts)

    Anything else returns ``None`` so non-revenue voucher types
    (Receipt, Payment, Contra, Journal, Stock Journal, Delivery
    Note, etc.) are silently dropped.

    Order matters: credit / debit note checks come before the
    generic Sales / Purchase ones so ``Credit Note`` doesn't get
    mis-classified as a plain sales voucher.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    # Returns / credit notes / debit notes — match first because they
    # would otherwise hit the generic Sales/Purchase patterns below.
    if _VCH_PREFIX_CREDIT_NOTE.match(text) or \
            _VCH_PREFIX_SALES_RETURN.match(text):
        return (config.VCH_SALES, True)
    if _VCH_PREFIX_DEBIT_NOTE.match(text) or \
            _VCH_PREFIX_PURCHASE_RETURN.match(text):
        return (config.VCH_EXPENSE, True)
    # Regular sales / purchase
    if _VCH_PREFIX_SALES.match(text):
        return (config.VCH_SALES, False)
    if _VCH_PREFIX_PURCHASE.match(text):
        return (config.VCH_EXPENSE, False)
    return None


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


_AMT_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_amount(raw: str) -> float:
    """Parse a Tally AMOUNT field, including foreign-currency variants.

    Common shapes:

    * Plain: -82600.00 or 70000.00 — negative = Debit in Tally.
    * Forex: $ 1000.00 @ 80.00/Re = -80000.00 — the INR-converted
      value sits after the = sign; we want that. (The voucher is
      booked in INR for our P&L.)
    * Forex with no =: fall back to picking the largest-magnitude
      number, which is almost always the INR value (foreign currency
      values are typically smaller).

    Returns 0.0 for anything we genuinely cannot parse so the caller
    skips the entry — but we work hard to avoid that, because returning
    0 silently drops the voucher from the partner P&L (the bug behind
    "USD invoices not picked up").
    """
    if not raw:
        return 0.0
    text = raw.strip()
    if not text:
        return 0.0
    # Plain numeric fast path. Strip spaces + non-breaking spaces (�)
    # that Tally sometimes embeds in amount strings.
    cleaned = text.replace(",", "").replace(" ", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        pass
    # Forex form: take the value after the last '='.
    if "=" in text:
        right = text.rsplit("=", 1)[1].strip()
        right_clean = right.replace(",", "").replace(" ", "").replace(" ", "")
        try:
            return float(right_clean)
        except ValueError:
            pass
    # Last resort: pull every signed number, pick the largest-magnitude.
    # (Foreign currency values are typically smaller than INR.)
    nums = _AMT_NUMBER.findall(text.replace(",", ""))
    if nums:
        try:
            return max((float(n) for n in nums), key=abs)
        except ValueError:
            pass
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
    classification = _classify_vch_type(vch_type_raw)
    if classification is None:
        return None
    kind, is_return = classification
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

    # Which side of the voucher carries the items we care about?
    # Normal sales:   revenue on Credit side  (party Dr, revenue Cr)
    # Credit Note:    revenue on Debit side   (party Cr, revenue Dr — reversal)
    # Normal purchase: expense on Debit side  (expense Dr, party Cr)
    # Debit Note:     expense on Credit side  (expense Cr, party Dr — reversal)
    if kind == config.VCH_SALES:
        items_on_credit = not is_return
    else:                                                  # VCH_EXPENSE
        items_on_credit = is_return

    # Returns store amounts as NEGATIVE so they naturally subtract from
    # the running revenue / expense totals — every SUMIFS in the MIS
    # workbook then handles them correctly without any per-row flag.
    sign_mult = -1.0 if is_return else 1.0

    for entry in _children_named(velem, ["allledgerentries.list",
                                          "ledgerentries.list"]):
        ledger = _text(_find_first(entry, ["ledgername"]))
        if not ledger:
            continue
        amount = _parse_amount(_text(_find_first(entry, ["amount"])))
        # Tally's AMOUNT sign: positive = Credit, negative = Debit.
        is_credit = amount > 0
        if items_on_credit and not is_credit:
            continue                    # debit-side party ledger — skip
        if (not items_on_credit) and is_credit:
            continue                    # credit-side party ledger — skip
        amt_abs = abs(amount)
        if amt_abs == 0:
            continue
        cc_name = _ledger_cost_centre(entry)
        voucher.line_splits.append(VoucherLine(
            service=ledger,
            cost_centre=cc_name,
            amount=amt_abs * sign_mult,
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

    A single response can contain sales, purchase, credit-note, and
    debit-note vouchers — the ``file_type`` on the result reflects the
    dominant kind. Caller may want to split per kind before commit (we
    provide :func:`split_by_kind` for that).

    A warning listing **skipped voucher type names + counts** is appended
    when types are present that we don't classify (Receipt, Payment,
    Journal, Contra, etc., plus anything our prefix regexes don't catch).
    This is the diagnostic for "Tally has X vouchers but we picked up Y"
    — the operator can see exactly what we dropped.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = _parse_xml(xml)

    vouchers: list[ParsedVoucher] = []
    skipped: dict[str, int] = {}
    for velem in root.iter():
        if _norm_tag(velem.tag) != "voucher":
            continue
        v = _voucher_from_xml(velem)
        if v is not None:
            vouchers.append(v)
        else:
            vt = (velem.get("VCHTYPE")
                  or _text(_find_first(velem, ["vouchertypename"]))
                  or "(no type)")
            skipped[vt] = skipped.get(vt, 0) + 1

    result = ParseResult(file_type=config.FILE_TYPE_SALES)
    result.vouchers = vouchers
    if not vouchers:
        result.warnings.append(
            "No sales / purchase / credit-note / debit-note vouchers in "
            "the Tally response for this period. Confirm Tally has the "
            "right company loaded and that the date range covers at least "
            "one voucher.")
    if skipped:
        # Sort by count desc, list top types so the operator sees the
        # most impactful skips first.
        top = sorted(skipped.items(), key=lambda kv: -kv[1])
        summary = ", ".join(f"{vt}={n}" for vt, n in top[:8])
        result.warnings.append(
            f"Skipped {sum(skipped.values())} non-revenue voucher(s): "
            f"{summary}. If any of these are revenue/expense types we "
            f"should support, share the name and we'll add it.")
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
