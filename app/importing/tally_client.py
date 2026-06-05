"""Talk to Tally's local HTTP/XML gateway.

Tally Prime / ERP 9 ship with a built-in HTTP server. When the operator
enables it (F1 -> Settings -> Connectivity -> Tally is acting as: Both /
Server), Tally listens on a local port (default 9000) and accepts XML
``ENVELOPE`` requests describing what to export. No paid API key, no
internet, no cloud — everything stays on the operator's PC.

This module owns:

* envelope construction for the requests we need (current company, list
  of companies, day book fetch)
* HTTP POST + response decoding
* a small ``settings`` helper for the Tally URL (operator-configurable
  via the Settings page; default ``http://localhost:9000``)

The XML-to-data conversion lives in :mod:`.tally_xml` so we can swap
transports (e.g. unit-test the parser independently of the network).
"""

from __future__ import annotations

import datetime as _dt
import socket
from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

from ..database import transaction
from . import tally_xml
from .models import ParseResult


# ----------------------------- settings -------------------------------------

TALLY_URL_KEY = "tally_url"
DEFAULT_TALLY_URL = "http://localhost:9000"

# Tally typically takes ~1s for small periods; large periods (several
# thousand vouchers) can take a few seconds. 30s is a comfortable cap.
DEFAULT_TIMEOUT = 30.0


def get_tally_url() -> str:
    with transaction() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (TALLY_URL_KEY,)).fetchone()
    return (row["value"] if row and row["value"] else DEFAULT_TALLY_URL).strip()


def set_tally_url(url: str) -> None:
    url = (url or "").strip() or DEFAULT_TALLY_URL
    with transaction() as conn:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (TALLY_URL_KEY, url))


# --------------------------- envelope builders ------------------------------

def _tally_date(d: _dt.date) -> str:
    """Tally accepts dates as ``YYYYMMDD`` strings in static variables."""
    return d.strftime("%Y%m%d")


def envelope_current_company() -> str:
    """Ask Tally which company is currently loaded.

    Tally Prime exposes this via the ``$$CmpCurrentName`` formula. We use a
    tiny ``Object`` export so the response is small and fast — useful for
    'is Tally even reachable?' health checks.
    """
    return _ENV_CURRENT_COMPANY


def envelope_list_companies() -> str:
    """Ask Tally for every company currently loaded.

    Tally Prime can load multiple companies simultaneously, though only one
    is 'in focus' for new entries. The MIS app uses this to populate a
    dropdown when more than one is open.
    """
    return _ENV_LIST_COMPANIES


def envelope_day_book(from_date: _dt.date, to_date: _dt.date,
                     company_name: str | None = None) -> str:
    """Day-Book XML export for a date range.

    Tally returns every voucher in the period with full ledger + cost
    centre breakdowns — exactly what :mod:`.tally_xml` needs. Setting
    ``EXPLODEFLAG=Yes`` makes sure the indented ledger / CC lines come
    through (otherwise some Tally builds emit a flat 1-line voucher).
    """
    parts = [
        '<ENVELOPE>',
        '  <HEADER>',
        '    <VERSION>1</VERSION>',
        '    <TALLYREQUEST>Export</TALLYREQUEST>',
        '    <TYPE>Data</TYPE>',
        '    <ID>Day Book</ID>',
        '  </HEADER>',
        '  <BODY>',
        '    <DESC>',
        '      <STATICVARIABLES>',
        '        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>',
        f'        <SVFROMDATE TYPE="Date">{_tally_date(from_date)}</SVFROMDATE>',
        f'        <SVTODATE TYPE="Date">{_tally_date(to_date)}</SVTODATE>',
        '        <EXPLODEFLAG>Yes</EXPLODEFLAG>',
    ]
    if company_name:
        # Tally is case-sensitive on company names and any '&' must be
        # escaped — this is the operator-visible name from File > Select
        # Company in Tally.
        parts.append(
            f'        <SVCURRENTCOMPANY>{_xml_escape(company_name)}'
            f'</SVCURRENTCOMPANY>')
    parts += [
        '      </STATICVARIABLES>',
        '    </DESC>',
        '  </BODY>',
        '</ENVELOPE>',
    ]
    return "\n".join(parts)


def _xml_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# These two are static — no parameters — so we just inline them.
_ENV_CURRENT_COMPANY = """\
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>BMC_CurrentCompany</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="BMC_CurrentCompany" ISMODIFY="No">
            <TYPE>Company</TYPE>
            <FETCH>NAME, STARTINGFROM, ENDINGAT</FETCH>
            <FILTER>BMC_IsCurrent</FILTER>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="BMC_IsCurrent">$$IsEqual:$Name:##SVCurrentCompany</SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
"""

_ENV_LIST_COMPANIES = """\
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>BMC_AllCompanies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="BMC_AllCompanies" ISMODIFY="No">
            <TYPE>Company</TYPE>
            <FETCH>NAME, STARTINGFROM, ENDINGAT, ISACTIVE</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
"""


# ----------------------------- transport ------------------------------------

class TallyError(Exception):
    """Raised on any Tally communication failure."""


def _resolve_url(url: str | None) -> str:
    url = (url or get_tally_url()).strip()
    if not url:
        return DEFAULT_TALLY_URL
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def _post(envelope: str, url: str | None = None,
          timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """POST an XML envelope to Tally and return the raw response bytes."""
    full_url = _resolve_url(url)
    try:
        r = requests.post(full_url, data=envelope.encode("utf-8"),
                          headers={"Content-Type": "text/xml; charset=utf-8"},
                          timeout=timeout)
    except requests.ConnectionError as exc:
        raise TallyError(
            f"Couldn't connect to Tally at {full_url}. Is Tally open and is "
            "the HTTP server enabled? (Tally Prime: F1 -> Settings -> "
            "Connectivity -> Tally is acting as: Both, Port 9000)") from exc
    except requests.Timeout as exc:
        raise TallyError(
            f"Tally at {full_url} did not respond within {timeout:.0f}s. "
            "If the period is large, try a smaller date range.") from exc
    except requests.RequestException as exc:
        raise TallyError(f"Tally request failed: {exc}") from exc

    if r.status_code != 200:
        raise TallyError(
            f"Tally returned HTTP {r.status_code}. Body: {r.text[:300]}")
    return r.content


# ----------------------------- public API -----------------------------------

@dataclass
class TallyCompanyInfo:
    name: str
    books_from: _dt.date | None = None
    books_to: _dt.date | None = None
    is_active: bool = True


def ping(url: str | None = None,
         timeout: float = 5.0) -> bool:
    """Quick TCP probe so the UI can show 'connected' before sending a
    real request. Returns True if the host:port accepts a TCP connection.
    """
    parsed = urlparse(_resolve_url(url))
    host = parsed.hostname or "localhost"
    port = parsed.port or 9000
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def current_company(url: str | None = None) -> TallyCompanyInfo | None:
    """Return the currently-loaded Tally company (or None if none is)."""
    raw = _post(envelope_current_company(), url=url, timeout=10.0)
    return _parse_company_response(raw, first_only=True)


def list_companies(url: str | None = None) -> list[TallyCompanyInfo]:
    """Return every company Tally has loaded right now."""
    raw = _post(envelope_list_companies(), url=url, timeout=10.0)
    return _parse_company_response(raw, first_only=False) or []


def fetch_day_book(from_date: _dt.date, to_date: _dt.date,
                   company_name: str | None = None,
                   url: str | None = None) -> ParseResult:
    """Pull every sales + purchase voucher in the period and parse it.

    Returns a single :class:`ParseResult` mixing both kinds; callers split
    via :func:`tally_xml.split_by_kind` before commit so each batch lands
    with the right ``file_type`` label.

    On a parse failure (Tally returned malformed XML we don't yet handle),
    the raw bytes are dumped to ``<DATA_DIR>/tally_debug_YYYYMMDD-HHMMSS.xml``
    so the operator can share it with us to reproduce the issue offline.
    """
    if from_date > to_date:
        raise ValueError("from_date is after to_date")
    raw = _post(envelope_day_book(from_date, to_date, company_name), url=url)
    try:
        return tally_xml.parse_response(raw)
    except ET.ParseError as exc:
        debug_path = _dump_debug_response(raw)
        raise TallyError(
            f"Tally returned XML the parser couldn't read ({exc}). "
            f"Raw response saved to {debug_path} — please share it so we "
            "can teach the parser the new layout.") from exc


def _dump_debug_response(raw: bytes) -> str:
    """Write a problematic Tally response to the data dir for triage."""
    from .. import config
    config.ensure_dirs()
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = config.DATA_DIR / f"tally_debug_{stamp}.xml"
    try:
        path.write_bytes(raw)
        return str(path)
    except OSError:
        return "<could not write debug file>"


# ---------------------------- xml helpers -----------------------------------

def _parse_company_response(xml: bytes,
                             first_only: bool) -> (TallyCompanyInfo
                                                   | list[TallyCompanyInfo]
                                                   | None):
    """Tally returns ``<COMPANY>`` collection items under ``<ENVELOPE>``."""
    try:
        root = tally_xml._parse_xml(xml)
    except ET.ParseError:
        if first_only:
            return None
        return []

    found: list[TallyCompanyInfo] = []
    for elem in root.iter():
        if tally_xml._norm_tag(elem.tag) != "company":
            continue
        # Tally puts the name either as an attribute or as a child <NAME>.
        name = (elem.get("NAME") or "").strip()
        if not name:
            name_el = tally_xml._find_first(elem, ["name"])
            name = tally_xml._text(name_el)
        if not name:
            continue
        books_from = tally_xml._parse_tally_date(
            tally_xml._text(tally_xml._find_first(elem, ["startingfrom"])))
        books_to = tally_xml._parse_tally_date(
            tally_xml._text(tally_xml._find_first(elem, ["endingat"])))
        is_active = (tally_xml._text(
            tally_xml._find_first(elem, ["isactive"])).lower() != "no")
        found.append(TallyCompanyInfo(
            name=name, books_from=books_from, books_to=books_to,
            is_active=is_active))

    if first_only:
        return found[0] if found else None
    return found
