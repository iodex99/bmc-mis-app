"""MIS workbook generator — a formula-driven, board-ready Excel file.

Design: the raw revenue / expense / labour facts are written to data sheets;
every summary number on the P&L and dashboard sheets is an Excel ``SUMIFS`` (or
arithmetic) formula referencing those data sheets. Open the workbook, tweak a
data row, and every report number recalculates — nothing is hard-coded.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .. import config
from ..database import transaction
from ..util import fmt_inr
from .calc import (
    EXPENSE_TYPE_INDIRECT,
    EXPENSE_TYPE_PROFESSIONAL,
    MISData,
    expense_type,
    financial_year,
)
from .resolution import norm

# --- palette & formats -------------------------------------------------------

NAVY = "1F2A44"
BLUE = "2F7DF6"
LIGHT = "EAF0FB"
GREY = "F0F1F4"
# Indian lakh/crore grouping, right-sized per value magnitude so small numbers
# don't pick up phantom commas. Escaped commas (``\,``) in an Excel format
# string are literal — they render even when the preceding ``#`` placeholder
# has no digit to fill. The previous one-size-fits-crore format meant a
# ``1,500`` cell would show garbage commas on screen. Tiered conditional
# sections keep each magnitude clean:
#   - ≥ 1 crore (10000000) → ``1,23,45,678``
#   - ≥ 1 lakh (100000)    → ``1,23,456``
#   - < 1 lakh             → ``1,500`` (standard 3-digit grouping)
# Excel allows max 3 conditional numeric sections, so big-negative red
# styling was dropped — negatives render in regular grouping with a minus.
INR = (r'[>=10000000]##\,##\,##\,##0;'
       r'[>=100000]##\,##\,##0;'
       r'##,##0')
PCT = '0.0%'
HOURS = '#,##0.0'

_TITLE = Font(name="Segoe UI", size=15, bold=True, color=NAVY)
_SUB = Font(name="Segoe UI", size=10, italic=True, color="5B6577")
_HEAD = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
_BOLD = Font(name="Segoe UI", size=10, bold=True)
_NORMAL = Font(name="Segoe UI", size=10)
_KPI = Font(name="Segoe UI", size=18, bold=True, color=NAVY)

_HEAD_FILL = PatternFill("solid", fgColor=NAVY)
_SUBHEAD_FILL = PatternFill("solid", fgColor="3D4E70")
_TOTAL_FILL = PatternFill("solid", fgColor=LIGHT)
_SECTION_FILL = PatternFill("solid", fgColor="DEE5F1")
_KPI_FILL = PatternFill("solid", fgColor=GREY)


# Heuristic — what counts as "Reimbursement / OPE" income vs Sales income.
# Used to populate the Category column on the Revenue data sheet so the
# Partner-Manager P&L can split "Sales" from "Reimb & OPE" via SUMIFS.

_REIMB_KEYWORDS = ("reimbur",)
_OPE_KEYWORDS = ("out of pocket", "out-of-pocket", " ope", "oop")
_OTHER_KEYWORDS = ("round off", "roundoff", "round-off")


def _service_category(name: str) -> str:
    if not name:
        return "Income"
    s = name.lower()
    if any(k in s for k in _REIMB_KEYWORDS):
        return "Reimbursement"
    if any(k in s for k in _OPE_KEYWORDS) or s.strip() in ("ope",):
        return "OPE"
    if any(k in s for k in _OTHER_KEYWORDS):
        return "Other"
    return "Income"
_thin = Side(style="thin", color="D2D6DE")
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
_CENTER = Alignment(horizontal="center", vertical="center")
_RIGHT = Alignment(horizontal="right")


def _q(sheet: str) -> str:
    """Quote a sheet name for use inside a formula."""
    return f"'{sheet}'"


# --- generic cell helpers ----------------------------------------------------

def _cell(ws, row, col, value, *, font=_NORMAL, fill=None, fmt=None,
          align=None, border=False):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font
    if fill:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if align:
        c.alignment = align
    if border:
        c.border = _BORDER
    return c


def _header_row(ws, row, headers, start_col=1):
    for i, text in enumerate(headers):
        _cell(ws, row, start_col + i, text, font=_HEAD, fill=_HEAD_FILL,
              align=_CENTER, border=True)


# --- master label maps -------------------------------------------------------

def _labels() -> dict:
    with transaction() as conn:
        cc = {r["id"]: r["code"]
              for r in conn.execute("SELECT id, code FROM cost_centres")}
        cc_active = [dict(r) for r in conn.execute(
            "SELECT id, code, name, cc_type FROM cost_centres "
            "WHERE active = 1 ORDER BY cc_type, code")]
        mgr = {r["id"]: r["code"]
               for r in conn.execute("SELECT id, code FROM managers")}
        ent = {r["id"]: r["name"]
               for r in conn.execute("SELECT id, name FROM entities")}
        svc = {r["id"]: r["name"]
               for r in conn.execute("SELECT id, name FROM services")}
        cli = {r["id"]: r["canonical_name"]
               for r in conn.execute("SELECT id, canonical_name FROM clients")}
    return {"cc": cc, "cc_active": cc_active, "mgr": mgr, "ent": ent,
            "svc": svc, "cli": cli}


# =============================== generation =================================

def generate(data: MISData, path: str | Path,
             compare: MISData | None = None) -> Path:
    """Write the full MIS workbook for *data* to *path*.

    When *compare* (a second MISData for a prior period) is given, a
    Comparatives sheet plus its own data sheets are added.
    """
    lbl = _labels()
    wb = Workbook()
    wb.remove(wb.active)

    _sheet_cover(wb, data, compare)
    _sheet_dashboard(wb, data)
    _sheet_budget_monthly(wb, data, lbl)
    rows_pl = _sheet_cost_centre(wb, data, lbl)
    _sheet_partner_manager(wb, data, lbl)
    _sheet_entity(wb, data, lbl)
    _sheet_service(wb, data, lbl)
    _sheet_client_billing(wb, data, lbl)
    _sheet_employee_register(wb, data, lbl)
    if compare is not None:
        _sheet_comparatives(wb, data, compare, lbl, rows_pl)
    _sheet_revenue(wb, data, lbl)
    _sheet_expenses(wb, data, lbl)
    _sheet_salary(wb, data, lbl)
    _sheet_reimbursements(wb, data, lbl)
    if compare is not None:
        _sheet_revenue(wb, compare, lbl, CMP)
        _sheet_expenses(wb, compare, lbl, CMP)
        _sheet_salary(wb, compare, lbl, CMP)
        _sheet_reimbursements(wb, compare, lbl, CMP)

    # Dashboard KPIs link to the Cost Centre P&L total row.
    _link_dashboard(wb, rows_pl)

    path = Path(path)
    wb.save(path)
    return path


CMP = " (Cmp)"   # suffix for comparison-period data sheets


# --- Cover -------------------------------------------------------------------

def _sheet_cover(wb: Workbook, data: MISData,
                 compare: MISData | None = None) -> None:
    ws = wb.create_sheet("Cover")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 70

    _cell(ws, 2, 2, config.ORG_NAME, font=Font(size=20, bold=True, color=NAVY))
    _cell(ws, 3, 2, "Management Information System",
          font=Font(size=13, color=BLUE))
    periods = ", ".join(data.options.periods)
    rows = [
        ("Reporting period(s)", periods),
        ("Comparison period(s)",
         ", ".join(compare.options.periods) if compare else "—"),
        ("Generated on", _dt.date.today().strftime("%d %b %Y")),
        ("Reimbursements in MIS",
         "Included" if data.options.include_reimbursement else "Excluded"),
        ("Office overhead basis",
         "Office indirect expenses ÷ active employees"),
        ("Total revenue", fmt_inr(data.total_revenue)),
        ("Total cost", fmt_inr(data.total_cost)),
        ("Net profit", fmt_inr(data.total_profit)),
    ]
    for i, (k, v) in enumerate(rows):
        r = 6 + i
        _cell(ws, r, 2, k, font=_BOLD)
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="left")
        _cell(ws, r, 2, k, font=_BOLD)
        c = ws.cell(row=r, column=2)
        c.value = k
        d = ws.cell(row=r, column=3, value=v)
        d.font = _NORMAL
    ws.column_dimensions["C"].width = 32
    for w in data.warnings:
        ws.append([])
    if data.warnings:
        _cell(ws, 16, 2, "Notes:", font=_BOLD)
        for i, w in enumerate(data.warnings):
            _cell(ws, 17 + i, 2, "• " + w, font=_SUB)


# --- Dashboard ---------------------------------------------------------------

def _sheet_dashboard(wb: Workbook, data: MISData) -> None:
    ws = wb.create_sheet("Dashboard")
    ws.sheet_view.showGridLines = False
    for col, width in (("A", 3), ("B", 26), ("C", 22), ("D", 26), ("E", 22)):
        ws.column_dimensions[col].width = width

    _cell(ws, 2, 2, "MIS Dashboard", font=_TITLE)
    _cell(ws, 3, 2, "Period(s): " + ", ".join(data.options.periods), font=_SUB)

    # KPI tiles — values filled later by _link_dashboard.
    tiles = [("Total Revenue", 5, 2), ("Total Cost", 5, 4),
             ("Net Profit", 8, 2), ("Total Target", 8, 4)]
    for label, r, c in tiles:
        _cell(ws, r, c, label, font=_BOLD, fill=_KPI_FILL)
        ws.cell(row=r, column=c + 1).fill = _KPI_FILL
        kpi = _cell(ws, r + 1, c, 0, font=_KPI, fill=_KPI_FILL, fmt=INR)
        ws.cell(row=r + 1, column=c + 1).fill = _KPI_FILL
        ws.merge_cells(start_row=r + 1, start_column=c,
                       end_row=r + 1, end_column=c + 1)
        kpi.alignment = Alignment(horizontal="left", vertical="center")

    _cell(ws, 12, 2, "See 'Cost Centre P&L' for the full partner-wise "
          "profitability and target comparison.", font=_SUB)


def _link_dashboard(wb: Workbook, rows_pl: dict) -> None:
    ws = wb["Dashboard"]
    pl = _q("Cost Centre P&L")
    total = rows_pl["total_row"]
    mapping = {
        (6, 2): f"={pl}!{rows_pl['col_revenue']}{total}",
        (6, 4): f"={pl}!{rows_pl['col_totalcost']}{total}",
        (9, 2): f"={pl}!{rows_pl['col_profit']}{total}",
        (9, 4): f"={pl}!{rows_pl['col_target']}{total}",
    }
    for (r, c), formula in mapping.items():
        cell = ws.cell(row=r, column=c, value=formula)
        cell.font = _KPI
        cell.number_format = INR


# --- Budget vs Monthly Sales -------------------------------------------------

def _fy_months_through(fy: str, end_period: str) -> list[str]:
    """All FY months (Apr-start to Mar-end) up to and including *end_period*.

    Indian financial year, e.g. ``fy='2025-26'`` → ``['2025-04', ..., '2026-03']``.
    Truncated to *end_period* (so a Jan run shows Apr-Jan, not the empty
    Feb-Mar months ahead).
    """
    try:
        start_year = int(fy.split('-')[0])
    except (ValueError, IndexError):
        return []
    months = [f"{start_year:04d}-{m:02d}" for m in range(4, 13)]
    months += [f"{start_year + 1:04d}-{m:02d}" for m in range(1, 4)]
    if end_period in months:
        return months[:months.index(end_period) + 1]
    return months


def _month_short(period: str) -> str:
    """``'2025-04'`` → ``'Apr 25'`` for compact column headers."""
    try:
        return _dt.date(int(period[:4]), int(period[5:7]), 1) \
            .strftime("%b %y")
    except (ValueError, IndexError):
        return period


def _sheet_budget_monthly(wb: Workbook, data: MISData, lbl: dict) -> None:
    """Year-to-date monthly sales per partner cost centre, vs annual budget.

    Independent of the selected MIS period: always shows the full FY-to-date
    picture so the board sees trend context alongside the headline P&L.
    Monthly cells are values (read from DB) since the Revenue data sheet only
    contains the selected periods; totals/variance/average are formulas so
    edits still recalculate.
    """
    if not data.options.periods:
        return
    latest = max(data.options.periods)
    fy = financial_year(latest)
    months = _fy_months_through(fy, latest)
    partners = [c for c in lbl["cc_active"] if c["cc_type"] == "partner"]
    if not months or not partners:
        return

    placeholders = ','.join('?' * len(months))
    with transaction() as conn:
        sales_rows = conn.execute(
            f"SELECT cc.code AS code, v.period AS period, "
            f"       COALESCE(SUM(s.amount), 0) AS amount "
            f"FROM voucher_splits s "
            f"JOIN vouchers v ON v.id = s.voucher_id "
            f"JOIN cost_centres cc ON cc.id = s.cost_centre_id "
            f"WHERE v.kind = 'sales' AND v.period IN ({placeholders}) "
            f"  AND cc.cc_type = 'partner' "
            f"GROUP BY cc.code, v.period",
            months).fetchall()
        budget_rows = conn.execute(
            "SELECT cc.code AS code, t.target_amount AS amount "
            "FROM targets t "
            "JOIN cost_centres cc ON cc.id = t.cost_centre_id "
            "WHERE t.financial_year = ?", (fy,)).fetchall()

    monthly: dict[str, dict[str, float]] = {}
    for row in sales_rows:
        monthly.setdefault(row["code"], {})[row["period"]] = row["amount"]
    budgets = {row["code"]: row["amount"] for row in budget_rows}

    ws = wb.create_sheet("Budget vs Monthly Sales")
    ws.sheet_view.showGridLines = False

    ws.column_dimensions["A"].width = 10  # Code
    ws.column_dimensions["B"].width = 26  # Cost Centre
    ws.column_dimensions["C"].width = 18  # Annual Budget
    for i, _ in enumerate(months):
        ws.column_dimensions[get_column_letter(4 + i)].width = 13
    ytd_col = 4 + len(months)
    var_col = ytd_col + 1
    avg_col = var_col + 1
    for col in (ytd_col, var_col, avg_col):
        ws.column_dimensions[get_column_letter(col)].width = 16

    _cell(ws, 1, 1, f"Budget vs Monthly Sales  —  FY {fy}", font=_TITLE)
    _cell(ws, 2, 1, "Year-to-date sales by partner cost centre. Annual budget "
                    "is read from the Targets master.", font=_SUB)

    headers = (["Code", "Cost Centre", "Annual Budget"]
               + [_month_short(m) for m in months]
               + ["YTD Total", "Variance vs Budget", "Avg / Active Month"])
    hrow = 4
    _header_row(ws, hrow, headers)

    body_start = hrow + 1
    r = body_start
    first_m = get_column_letter(4)
    last_m = get_column_letter(4 + len(months) - 1)
    ytd_L = get_column_letter(ytd_col)

    for partner in partners:
        code = partner["code"]
        _cell(ws, r, 1, code, border=True)
        _cell(ws, r, 2, partner["name"], border=True)
        _cell(ws, r, 3, round(budgets.get(code, 0.0), 2),
              fmt=INR, border=True)
        for i, period in enumerate(months):
            col = 4 + i
            amount = monthly.get(code, {}).get(period, 0.0)
            _cell(ws, r, col, round(amount, 2), fmt=INR, border=True)
        _cell(ws, r, ytd_col, f"=SUM({first_m}{r}:{last_m}{r})",
              font=_BOLD, fill=_TOTAL_FILL, fmt=INR, border=True)
        _cell(ws, r, var_col, f"=C{r}-{ytd_L}{r}", fmt=INR, border=True)
        _cell(ws, r, avg_col,
              f'=IFERROR({ytd_L}{r}/COUNTIF({first_m}{r}:{last_m}{r},'
              f'">0"),0)', fmt=INR, border=True)
        r += 1

    last_body = r - 1
    _cell(ws, r, 1, "", fill=_TOTAL_FILL, border=True)
    _cell(ws, r, 2, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
    for col in range(3, avg_col + 1):
        L = get_column_letter(col)
        if col == avg_col:
            formula = (f'=IFERROR({ytd_L}{r}/COUNTIF({first_m}{r}:{last_m}{r},'
                       f'">0"),0)')
        else:
            formula = f"=SUM({L}{body_start}:{L}{last_body})"
        _cell(ws, r, col, formula, font=_BOLD, fill=_TOTAL_FILL,
              fmt=INR, border=True)

    ws.freeze_panes = f"D{body_start}"


# --- Cost Centre P&L (the core sheet) ----------------------------------------

def _sheet_cost_centre(wb: Workbook, data: MISData, lbl: dict) -> dict:
    ws = wb.create_sheet("Cost Centre P&L")
    ws.sheet_view.showGridLines = False
    headers = ["Code", "Cost Centre", "Revenue", "Direct Expense",
               "Salary Cost", "Allocated Overhead", "Total Cost", "Profit",
               "Target", "Variance", "Profit %"]
    widths = [10, 26, 16, 16, 16, 18, 16, 16, 16, 16, 11]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(1 + i)].width = w

    _cell(ws, 1, 1, "Cost Centre Profitability", font=_TITLE)
    _cell(ws, 2, 1, "Period(s): " + ", ".join(data.options.periods), font=_SUB)
    hrow = 4
    _header_row(ws, hrow, headers)

    # All active cost centres (partners first, Office last), plus an
    # 'Unassigned' line if any fact lacks a cost centre.
    partners = [c for c in lbl["cc_active"] if c["cc_type"] != "office"]
    office = [c for c in lbl["cc_active"] if c["cc_type"] == "office"]
    targets = {c.cost_centre_id: c.target for c in data.cost_centres}
    has_unassigned = any(c.cost_centre_id is None for c in data.cost_centres)

    rev = _q("Revenue")
    exp = _q("Expenses")
    lab = _q("Salary")
    reimb = _q("Reimbursements")
    first = hrow + 1
    n_partners = len(partners)
    # Row order: partners, then Office, then (optional) Unassigned.
    n = n_partners + len(office) + (1 if has_unassigned else 0)
    last = first + n - 1
    total_row = last + 1

    def write_row(r, code, name, target, kind):
        _cell(ws, r, 1, code, font=_NORMAL, border=True)
        _cell(ws, r, 2, name, font=_NORMAL, border=True)
        # Revenue: SUMIFS over the Revenue sheet (col H = Amount).
        _cell(ws, r, 3, f"=SUMIFS({rev}!$H:$H,{rev}!$D:$D,$A{r})",
              fmt=INR, border=True)
        # Direct Expense: voucher-driven expenses + reimbursement rows
        # (the latter booked to the client's CC). Expenses layout
        # v0.3.69: Amount=J, CostCentre=E.
        _cell(ws, r, 4,
              f"=SUMIFS({exp}!$J:$J,{exp}!$E:$E,$A{r})"
              f"+SUMIFS({reimb}!$G:$G,{reimb}!$C:$C,$A{r})",
              fmt=INR, border=True)
        # Salary Cost: ONLY the Salary-type rows of the Salary sheet
        # (Type column = "Salary"). Office overhead is broken out
        # separately into the Allocated Overhead column.
        _cell(ws, r, 5,
              f'=SUMIFS({lab}!$I:$I,{lab}!$C:$C,$A{r},'
              f'{lab}!$J:$J,"Salary")',
              fmt=INR, border=True)
        # Allocated Overhead: the Overhead-type rows of the Salary
        # sheet. Since v0.3.69 each ACTIVE employee carries one such
        # row of (office indirect expenses ÷ active employees) on
        # their home CC — see the Employee Register sheet for the
        # computation — and Office carries the negative offset so the
        # pool (already inside Office's Direct Expense) isn't counted
        # twice in the firm total.
        _cell(ws, r, 6,
              f'=SUMIFS({lab}!$I:$I,{lab}!$C:$C,$A{r},'
              f'{lab}!$J:$J,"Overhead")',
              fmt=INR, border=True)
        _cell(ws, r, 7, f"=D{r}+E{r}+F{r}", fmt=INR, border=True, font=_NORMAL)
        _cell(ws, r, 8, f"=C{r}-G{r}", fmt=INR, border=True)
        _cell(ws, r, 9, target or 0, fmt=INR, border=True)
        # Variance: Revenue − Target (v0.3.67). Pre-v0.3.67 was
        # Profit − Target which confused achievement-against-revenue-
        # target with operating profit margin.
        _cell(ws, r, 10, f"=C{r}-I{r}", fmt=INR, border=True)
        _cell(ws, r, 11, f"=IF(C{r}=0,0,H{r}/C{r})", fmt=PCT, border=True,
              align=_CENTER)

    row_of: dict[str, int] = {}
    r = first
    for c in partners:
        write_row(r, c["code"], c["name"], targets.get(c["id"], 0.0), "partner")
        row_of[c["code"]] = r
        r += 1
    for c in office:
        write_row(r, c["code"], c["name"], targets.get(c["id"], 0.0), "office")
        row_of[c["code"]] = r
        r += 1
    if has_unassigned:
        write_row(r, "Unassigned", "Unassigned / to be mapped", 0.0,
                  "unassigned")
        row_of["Unassigned"] = r
        r += 1

    # Total row.
    _cell(ws, total_row, 1, "", fill=_TOTAL_FILL)
    _cell(ws, total_row, 2, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
    for col in range(3, 12):
        L = get_column_letter(col)
        fmt = PCT if col == 11 else INR
        if col == 11:
            formula = f"=IF(C{total_row}=0,0,H{total_row}/C{total_row})"
        else:
            formula = f"=SUM({L}{first}:{L}{last})"
        _cell(ws, total_row, col, formula, font=_BOLD, fill=_TOTAL_FILL,
              fmt=fmt, border=True)

    ws.freeze_panes = f"A{first}"
    return {"first": first, "last": last, "total_row": total_row,
            "col_revenue": "C", "col_totalcost": "G", "col_profit": "H",
            "col_target": "I", "row_of": row_of}


# --- Partner – Manager P&L (matrix layout) ----------------------------------

def _build_pm_matrix(data: MISData, lbl: dict):
    """Build the partner-manager column structure for the P&L matrix.

    Returns a list of partner blocks, where each block is:
        (cc_code, cc_name, [(manager_label, manager_filter_value), …, ("Total", None)])

    *manager_filter_value* is the value to SUMIFS against the data sheet's
    Manager column. "(unassigned)" is used for splits the partner did
    directly without delegating to a named manager (so the first sub-column
    inside each partner block is the partner's "own" work).
    """
    cc_active_map = {c["id"]: c for c in lbl["cc_active"]}

    pairs: set[tuple[int, int | None]] = set()
    for f in data.revenue_facts + data.expense_facts + data.labour_facts:
        cc_id = f.get("cost_centre_id")
        if cc_id is None:
            continue
        mgr_id = f.get("manager_id")  # labour facts have no manager — fine
        pairs.add((cc_id, mgr_id))

    by_partner: dict[int, list] = {}
    for cc_id, mgr_id in pairs:
        cc = cc_active_map.get(cc_id)
        if cc is None or cc["cc_type"] != "partner":
            continue
        by_partner.setdefault(cc_id, []).append(mgr_id)

    result = []
    for cc_id in sorted(by_partner.keys(),
                        key=lambda i: cc_active_map[i]["code"]):
        cc = cc_active_map[cc_id]
        mgr_ids = set(by_partner[cc_id])
        managers: list[tuple[str, str | None]] = []
        # "Self" — partner did the work directly (no manager named).
        if None in mgr_ids:
            managers.append((cc["code"], "(unassigned)"))
            mgr_ids.discard(None)
        # Then each named manager.
        for mgr_id in sorted(mgr_ids,
                             key=lambda m: lbl["mgr"].get(m, "?") or "?"):
            managers.append((lbl["mgr"].get(mgr_id, "?"),
                             lbl["mgr"].get(mgr_id)))
        # Per-partner subtotal column.
        managers.append(("Total", None))
        result.append((cc["code"], cc["name"], managers))
    return result


def _sheet_partner_manager(wb: Workbook, data: MISData, lbl: dict) -> None:
    """The headline P&L sheet — partner super-headers, manager sub-columns,
    formula-driven from the Revenue / Expenses / Labour data sheets."""
    ws = wb.create_sheet("Partner-Manager P&L")
    ws.sheet_view.showGridLines = False

    matrix = _build_pm_matrix(data, lbl)
    if not matrix:
        # Nothing to show — still draw a heading so the sheet isn't blank.
        _cell(ws, 1, 1, "Partner – Manager Profitability", font=_TITLE)
        _cell(ws, 3, 1,
              "No data yet — once you import sales / expenses / salary the "
              "full matrix will appear here.", font=_SUB)
        return

    # ---- Title + subtitle ----
    _cell(ws, 1, 1, "Partner – Manager Profitability", font=_TITLE)
    _cell(ws, 2, 1, "Period(s): " + ", ".join(data.options.periods),
          font=_SUB)

    # ---- Column layout ----
    # Col 1 = Particulars. Then each partner block contributes (len(managers))
    # columns. Final column = "MIS Total".
    block_starts: list[int] = []
    cols_per_block: list[int] = []
    col_idx = 2
    for cc_code, cc_name, managers in matrix:
        block_starts.append(col_idx)
        cols_per_block.append(len(managers))
        col_idx += len(managers)
    mis_total_col = col_idx
    last_col = mis_total_col

    # Set column widths.
    ws.column_dimensions["A"].width = 30
    for col in range(2, last_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14

    # ---- Header rows ----
    hdr_partner_row = 4
    hdr_mgr_row = 5
    body_start = 7

    # Partner super-header (row 4): merged across each block's columns.
    for (cc_code, cc_name, managers), start, count in zip(
            matrix, block_starts, cols_per_block):
        end = start + count - 1
        ws.merge_cells(start_row=hdr_partner_row, start_column=start,
                       end_row=hdr_partner_row, end_column=end)
        _cell(ws, hdr_partner_row, start, cc_name, font=_HEAD,
              fill=_HEAD_FILL, align=_CENTER, border=True)
        for col in range(start, end + 1):
            ws.cell(row=hdr_partner_row, column=col).fill = _HEAD_FILL
            ws.cell(row=hdr_partner_row, column=col).border = _BORDER
    _cell(ws, hdr_partner_row, mis_total_col, "MIS Total", font=_HEAD,
          fill=_HEAD_FILL, align=_CENTER, border=True)
    _cell(ws, hdr_partner_row, 1, "", fill=_HEAD_FILL)

    # Manager sub-header (row 5): one cell per manager column + Total.
    _cell(ws, hdr_mgr_row, 1, "Particulars", font=_HEAD, fill=_SUBHEAD_FILL,
          align=_CENTER, border=True)
    for (cc_code, cc_name, managers), start in zip(matrix, block_starts):
        for offset, (label, _filter) in enumerate(managers):
            _cell(ws, hdr_mgr_row, start + offset, label, font=_HEAD,
                  fill=_SUBHEAD_FILL, align=_CENTER, border=True)
    _cell(ws, hdr_mgr_row, mis_total_col, "Total", font=_HEAD,
          fill=_SUBHEAD_FILL, align=_CENTER, border=True)

    # ---- P&L lines ----
    rev, exp, lab = _q("Revenue"), _q("Expenses"), _q("Salary")
    reimb = _q("Reimbursements")

    # Returns the SUMIFS formula for a (partner, manager) cell on a given
    # data sheet's amount column.
    def sumifs(sheet_q, amount_col, cc_code, mgr_filter, extra=None,
               cc_col="D", mgr_col="E"):
        # Column layout on the data sheets (v0.3.69):
        #   Revenue:  A=Date B=VoucherNo C=Entity D=CostCentre E=Manager
        #             F=Service G=Client H=Amount I=Category
        #   Expenses: A=Date B=VoucherNo C=InvoiceNo D=Entity E=CostCentre
        #             F=Manager G=Service H=TypeOfExpense I=Client
        #             J=Amount K=Description L=Period
        parts = [
            f"{sheet_q}!${amount_col}:${amount_col}",
            f"{sheet_q}!${cc_col}:${cc_col}", f'"{cc_code}"',
        ]
        if mgr_filter is not None:
            parts.append(f"{sheet_q}!${mgr_col}:${mgr_col}")
            parts.append(f'"{mgr_filter}"')
        for col, value in (extra or []):
            parts.append(f"{sheet_q}!${col}:${col}")
            parts.append(f'"{value}"')
        return "=SUMIFS(" + ",".join(parts) + ")"

    def exp_sumifs(cc_code, mgr_filter, type_label):
        # Expense cells filter on the Type of Expense column (H) so the
        # P&L can split Professional Fees (direct) from Indirect
        # Expenses (shown under the overhead block).
        return sumifs(exp, "J", cc_code, mgr_filter,
                      extra=[("H", type_label)], cc_col="E", mgr_col="F")

    def labour_sumifs(cc_code):
        # Labour (salary) facts don't carry a manager, so cells under
        # a manager column just read the partner-level salary cost.
        # Attributed to the partner's "Self" (first) column only.
        # Filter by Type="Salary" so the Overhead facts (v0.3.67) don't
        # double-count here — they have their own dedicated row.
        return (f'=SUMIFS({lab}!$I:$I,{lab}!$C:$C,"{cc_code}",'
                f'{lab}!$J:$J,"Salary")')

    # Row layout. Each entry: (label, kind)
    # kinds:
    #   "sales"     -> Revenue, Category = Income
    #   "reimb"     -> Revenue, Category IN (Reimbursement, OPE)
    #   "salary"    -> Labour amount (partner-level only)
    #   "expense"   -> Expenses, Type = Professional Fees (DIRECT cost)
    #   "reimb_exp" -> Reimbursements sheet (partner-level only)
    #   "income_sum"-> SUM of sales + reimb rows
    #   "cost_sum"  -> SUM of salary + expense + reimb_exp rows
    #   "gross"     -> income_sum - cost_sum
    #   "gross_pct" -> gross / income
    #   "overhead"  -> Salary sheet, Type = Overhead (per-employee share
    #                  of office indirect costs — see Employee Register)
    #   "indirect"  -> Expenses, Type = Indirect Expense (the partner's
    #                  own indirect costs, NOT the office pool)
    #   "net"       -> gross - overhead - indirect
    #   "net_pct"   -> net / income
    # We track by row number for cross-referencing.
    plan = [
        ("Sales (Income)", "sales"),
        ("Reimbursement & OPE", "reimb"),
        ("Total Income", "income_sum"),
        ("", "blank"),
        ("Salary (labour cost)", "salary"),
        ("Professional Fees", "expense"),
        ("Reimbursement Expenses", "reimb_exp"),
        ("Total Direct Costs", "cost_sum"),
        ("", "blank"),
        ("Gross Profit", "gross"),
        ("Gross Profit %", "gross_pct"),
        ("", "blank"),
        ("Office Overhead (allocated)", "overhead"),
        ("Indirect Expenses", "indirect"),
        ("Net Profit", "net"),
        ("Net Profit %", "net_pct"),
    ]

    r = body_start
    rows_by_kind: dict[str, int] = {}
    for label, kind in plan:
        if kind == "blank":
            r += 1
            continue
        rows_by_kind[kind] = r
        is_total = kind in ("income_sum", "cost_sum", "gross", "gross_pct",
                            "net", "net_pct")
        font = _BOLD if is_total else _NORMAL
        fill = _TOTAL_FILL if is_total else None
        _cell(ws, r, 1, label, font=font, fill=fill, border=True)

        for (cc_code, cc_name, managers), start in zip(matrix, block_starts):
            for offset, (mgr_label, mgr_filter) in enumerate(managers):
                col = start + offset
                is_total_col = (offset == len(managers) - 1)
                cell_fmt = PCT if kind.endswith("_pct") else INR
                if is_total_col and kind == "gross_pct":
                    # Recompute the ratio at the partner level — summing
                    # percentages doesn't make sense.
                    inc_r = rows_by_kind["income_sum"]
                    gross_r = rows_by_kind["gross"]
                    L = get_column_letter(col)
                    formula = (f"=IF({L}{inc_r}=0,0,"
                               f"{L}{gross_r}/{L}{inc_r})")
                elif is_total_col and kind == "overhead":
                    # Allocated office overhead is partner-level, not
                    # manager-level — pull from the Salary sheet via
                    # SUMIFS on Type="Overhead" so it stays formula-
                    # driven (v0.3.67). Pre-v0.3.67 baked the computed
                    # number directly into the cell.
                    formula = (f'=SUMIFS({lab}!$I:$I,{lab}!$C:$C,'
                               f'"{cc_code}",{lab}!$J:$J,"Overhead")')
                elif is_total_col and kind == "net":
                    gross_r = rows_by_kind["gross"]
                    overhead_r = rows_by_kind["overhead"]
                    indirect_r = rows_by_kind["indirect"]
                    L = get_column_letter(col)
                    formula = (f"={L}{gross_r}-{L}{overhead_r}"
                               f"-{L}{indirect_r}")
                elif is_total_col and kind == "net_pct":
                    inc_r = rows_by_kind["income_sum"]
                    net_r = rows_by_kind["net"]
                    L = get_column_letter(col)
                    formula = (f"=IF({L}{inc_r}=0,0,"
                               f"{L}{net_r}/{L}{inc_r})")
                elif is_total_col:
                    # Plain SUM across the partner's manager columns.
                    from_col = start
                    to_col = start + len(managers) - 2
                    if from_col > to_col:
                        formula = 0
                    else:
                        formula = (f"=SUM({get_column_letter(from_col)}{r}:"
                                   f"{get_column_letter(to_col)}{r})")
                elif kind in ("overhead", "net", "net_pct"):
                    # Manager-level cells for overhead / net are blank —
                    # office overhead doesn't break down by manager.
                    formula = 0
                elif kind == "sales":
                    formula = sumifs(rev, "H", cc_code, mgr_filter,
                                     extra=[("I", "Income")])
                elif kind == "reimb":
                    # Reimbursement + OPE together — two SUMIFS summed.
                    f1 = sumifs(rev, "H", cc_code, mgr_filter,
                                extra=[("I", "Reimbursement")])
                    f2 = sumifs(rev, "H", cc_code, mgr_filter,
                                extra=[("I", "OPE")])
                    formula = "=" + f1[1:] + "+" + f2[1:]
                elif kind == "income_sum":
                    sales_r = rows_by_kind["sales"]
                    reimb_r = rows_by_kind["reimb"]
                    formula = (f"={get_column_letter(col)}{sales_r}+"
                               f"{get_column_letter(col)}{reimb_r}")
                elif kind == "salary":
                    # Labour cost is partner-level; attribute to "Self" col.
                    if offset == 0:
                        formula = labour_sumifs(cc_code)
                    else:
                        formula = 0
                elif kind == "expense":
                    # Professional fees bought in — the partner's DIRECT
                    # expense (operator ask v0.3.69; was "all expenses").
                    formula = exp_sumifs(cc_code, mgr_filter,
                                         EXPENSE_TYPE_PROFESSIONAL)
                elif kind == "indirect":
                    formula = exp_sumifs(cc_code, mgr_filter,
                                         EXPENSE_TYPE_INDIRECT)
                elif kind == "reimb_exp":
                    # Reimbursement outlays land on the client's partner —
                    # no manager dimension on that sheet, so partner-level
                    # ("Self" column) only. Keeps the P&L tying with the
                    # Cost Centre P&L's Direct Expense column.
                    if offset == 0:
                        formula = (f'=SUMIFS({reimb}!$G:$G,'
                                   f'{reimb}!$C:$C,"{cc_code}")')
                    else:
                        formula = 0
                elif kind == "cost_sum":
                    sal_r = rows_by_kind["salary"]
                    exp_r = rows_by_kind["expense"]
                    rexp_r = rows_by_kind["reimb_exp"]
                    L = get_column_letter(col)
                    formula = f"={L}{sal_r}+{L}{exp_r}+{L}{rexp_r}"
                elif kind == "gross":
                    inc_r = rows_by_kind["income_sum"]
                    cost_r = rows_by_kind["cost_sum"]
                    formula = (f"={get_column_letter(col)}{inc_r}-"
                               f"{get_column_letter(col)}{cost_r}")
                elif kind == "gross_pct":
                    inc_r = rows_by_kind["income_sum"]
                    gross_r = rows_by_kind["gross"]
                    L = get_column_letter(col)
                    formula = (f"=IF({L}{inc_r}=0,0,"
                               f"{L}{gross_r}/{L}{inc_r})")
                else:
                    formula = 0

                _cell(ws, r, col, formula, font=font, fill=fill, fmt=cell_fmt,
                      border=True)

        # MIS Total column — sum across each partner's "Total" sub-column.
        L = get_column_letter(mis_total_col)
        if kind == "gross_pct":
            inc_r = rows_by_kind["income_sum"]
            gross_r = rows_by_kind["gross"]
            mis_formula = (f"=IF({L}{inc_r}=0,0,"
                           f"{L}{gross_r}/{L}{inc_r})")
        elif kind == "net_pct":
            inc_r = rows_by_kind["income_sum"]
            net_r = rows_by_kind["net"]
            mis_formula = (f"=IF({L}{inc_r}=0,0,"
                           f"{L}{net_r}/{L}{inc_r})")
        else:
            total_refs = [f"{get_column_letter(start + count - 1)}{r}"
                          for start, count in zip(block_starts, cols_per_block)]
            mis_formula = "=" + "+".join(total_refs) if total_refs else 0
        _cell(ws, r, mis_total_col, mis_formula, font=_BOLD,
              fill=_TOTAL_FILL,
              fmt=PCT if kind.endswith("_pct") else INR, border=True)

        r += 1

    ws.freeze_panes = f"B{body_start}"
    _cell(ws, r + 1, 1,
          "Salary cost is allocated to partners via timesheet hours, not "
          "split by manager. Professional Fees / Indirect Expenses follow "
          "the Cost Center on the voucher split and the Type of Expense "
          "column on the Expenses sheet. Office Overhead = office indirect "
          "expenses ÷ active employees, charged to each active employee's "
          "home cost centre (see Employee Register).",
          font=_SUB)


# --- Entity & Service --------------------------------------------------------

def _sheet_entity(wb: Workbook, data: MISData, lbl: dict) -> None:
    # Entity is column C on Revenue, D on Expenses (v0.3.69 layout).
    _simple_summary(wb, "Entity P&L", "Entity-wise Profitability",
                    "Entity", data.entities, "ent", lbl, key="name",
                    sumcol_rev="C", sumcol_exp="D")


def _sheet_service(wb: Workbook, data: MISData, lbl: dict) -> None:
    # Service is column F on Revenue, G on Expenses (v0.3.69 layout).
    _simple_summary(wb, "Service MIS", "Service-wise Revenue & Cost",
                    "Service", data.services, "svc", lbl, key="name",
                    sumcol_rev="F", sumcol_exp="G")


def _sheet_client_billing(wb: Workbook, data: MISData, lbl: dict) -> None:
    """Client × period billing matrix.

    One row per client (canonical name from the master, or ``(unmapped)``
    when the voucher's party didn't resolve). One column per selected
    period plus a ``Grand Total`` column second from the left, mirroring
    the operator's reference layout. Cells sum the revenue (net amount)
    booked to that client × period. Credit / Debit Notes flow through
    with their signs intact so the net billing nets returns automatically.
    Sorted by Grand Total descending so the biggest clients sit at top.
    """
    if not data.options.periods:
        return
    periods = sorted(data.options.periods)

    # Group by resolved client; unresolved parties group by their raw
    # party name (one row per distinct vendor/client as Tally spells it)
    # instead of all lumping into a single "(unmapped)" bucket.
    agg: dict = {}
    names: dict = {}
    for f in data.revenue_facts:
        cid = f.get("client_id")
        if cid is not None:
            key = ("c", cid)
            names[key] = lbl["cli"].get(cid, "(unmapped)")
        else:
            party = (f.get("party_name") or "").strip()
            key = ("r", norm(party)) if party else ("u",)
            names[key] = party or "(unmapped)"
        bucket = agg.setdefault(key, {p: 0.0 for p in periods})
        bucket[f["period"]] = bucket.get(f["period"], 0.0) + float(f["amount"])

    if not agg:
        return

    # Build sortable list: (name, total, [per-period amounts])
    rows = []
    for key, per_period in agg.items():
        amounts = [round(per_period.get(p, 0.0), 2) for p in periods]
        total = round(sum(amounts), 2)
        rows.append((names[key], total, amounts))
    rows.sort(key=lambda r: -r[1])

    ws = wb.create_sheet("Client Billing")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 16
    for i in range(len(periods)):
        ws.column_dimensions[get_column_letter(3 + i)].width = 13

    _cell(ws, 1, 1, "Client-wise Billing", font=_TITLE)
    _cell(ws, 2, 1, "Period(s): " + ", ".join(periods), font=_SUB)
    hrow = 4
    headers = ["Client", "Grand Total"] + [_month_short(p) for p in periods]
    _header_row(ws, hrow, headers)

    body_start = hrow + 1
    r = body_start
    first_period_col = get_column_letter(3)
    last_period_col = get_column_letter(3 + len(periods) - 1)
    for name, _total, amounts in rows:
        _cell(ws, r, 1, name, border=True)
        # Grand Total is a SUM formula across the period columns —
        # not a baked-in value — so the operator can edit a cell and
        # the total updates live.
        _cell(ws, r, 2,
              f"=SUM({first_period_col}{r}:{last_period_col}{r})",
              font=_BOLD, fill=_TOTAL_FILL, fmt=INR, border=True)
        for i, amt in enumerate(amounts):
            _cell(ws, r, 3 + i, amt, fmt=INR, border=True)
        r += 1

    # TOTAL row
    last_body = r - 1
    if last_body >= body_start:
        _cell(ws, r, 1, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
        for col in range(2, 3 + len(periods)):
            L = get_column_letter(col)
            _cell(ws, r, col,
                  f"=SUM({L}{body_start}:{L}{last_body})",
                  font=_BOLD, fill=_TOTAL_FILL, fmt=INR, border=True)

    ws.freeze_panes = f"C{body_start}"


def _simple_summary(wb, sheet, title, label, rows, _mapname, lbl, key,
                    sumcol_rev, sumcol_exp):
    """Entity / Service style summary: name, revenue, expense, net."""
    ws = wb.create_sheet(sheet)
    ws.sheet_view.showGridLines = False
    headers = [label, "Revenue", "Direct Expense", "Net"]
    for i, w in enumerate([30, 16, 16, 16]):
        ws.column_dimensions[get_column_letter(1 + i)].width = w
    _cell(ws, 1, 1, title, font=_TITLE)
    hrow = 3
    _header_row(ws, hrow, headers)

    rev, exp = _q("Revenue"), _q("Expenses")
    r = hrow + 1
    first = r
    for item in rows:
        _cell(ws, r, 1, item["name"], border=True)
        # Revenue Amount = col H; Expenses Amount = col J (v0.3.69 layout —
        # Invoice No + Type of Expense pushed Amount from H to J; col H is
        # now the "Type of Expense" TEXT column, so summing it returns 0).
        _cell(ws, r, 2, f"=SUMIFS({rev}!$H:$H,{rev}!${sumcol_rev}:${sumcol_rev},$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 3, f"=SUMIFS({exp}!$J:$J,{exp}!${sumcol_exp}:${sumcol_exp},$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 4, f"=B{r}-C{r}", fmt=INR, border=True)
        r += 1
    if r > first:
        _cell(ws, r, 1, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
        for col in (2, 3, 4):
            L = get_column_letter(col)
            _cell(ws, r, col, f"=SUM({L}{first}:{L}{r - 1})", font=_BOLD,
                  fill=_TOTAL_FILL, fmt=INR, border=True)


# --- data sheets -------------------------------------------------------------

def _write_data_sheet(wb, name, headers, widths, rows):
    ws = wb.create_sheet(name)
    _header_row(ws, 1, headers)
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(1 + i)].width = w
    for ri, row in enumerate(rows, start=2):
        for ci, val in enumerate(row, start=1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font = _NORMAL
            if isinstance(val, (int, float)):
                c.number_format = INR if abs(val) >= 100 else HOURS
            elif isinstance(val, str) and val.startswith("="):
                # Formula cells (e.g. the Salary sheet's live Overhead
                # amounts) render with the money format.
                c.number_format = INR
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    return ws


def _client_or_party(lbl: dict, f: dict) -> str:
    """Client column value: master canonical name when the party is
    linked; otherwise the raw party name straight off the voucher (the
    vendor/client as Tally spells it). "(unmapped)" only when the
    voucher carried no party at all."""
    name = lbl["cli"].get(f.get("client_id"))
    if name:
        return name
    return (f.get("party_name") or "").strip() or "(unmapped)"


def _sheet_revenue(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    rows = []
    for f in data.revenue_facts:
        svc_name = lbl["svc"].get(f["service_id"], "(unspecified)")
        rows.append([
            _fmt_date(f.get("txn_date")),
            f.get("vch_no") or "",
            lbl["ent"].get(f["entity_id"], "(unspecified)"),
            lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
            lbl["mgr"].get(f["manager_id"], "(unassigned)"),
            svc_name,
            _client_or_party(lbl, f),
            round(f["amount"], 2),
            _service_category(svc_name),
        ])
    _write_data_sheet(
        wb, "Revenue" + suffix,
        ["Date", "Voucher No", "Entity", "CostCentre", "Manager",
         "Service", "Client", "Amount", "Category"],
        [12, 16, 24, 12, 12, 22, 28, 14, 14], rows)


def _sheet_expenses(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    # Column layout (v0.3.69):
    #   A Date          B Voucher No   C Invoice No   D Entity
    #   E CostCentre    F Manager      G Service      H Type of Expense
    #   I Client        J Amount       K Description  L Period
    #
    # Invoice No comes from the register's "New Ref" bill allocation
    # (the vendor's invoice number on the detailed Tally export).
    # Type of Expense bifurcates Professional Fees (direct cost) from
    # Indirect Expense — the P&Ls SUMIFS against column H.
    # Period (L) lets the Employee Register compute the per-period
    # office indirect pool with a SUMIFS.
    rows = []
    for f in data.expense_facts:
        svc_name = lbl["svc"].get(f["service_id"], "(unspecified)")
        rows.append([
            _fmt_date(f.get("txn_date")), f.get("vch_no") or "",
            f.get("invoice_no") or "",
            lbl["ent"].get(f["entity_id"], "(unspecified)"),
            lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
            lbl["mgr"].get(f["manager_id"], "(unassigned)"),
            svc_name,
            f.get("expense_type") or expense_type(svc_name),
            _client_or_party(lbl, f),
            round(f["amount"], 2), f.get("description", ""),
            f.get("period") or "",
        ])
    _write_data_sheet(wb, "Expenses" + suffix,
                      ["Date", "Voucher No", "Invoice No", "Entity",
                       "CostCentre", "Manager", "Service", "Type of Expense",
                       "Client", "Amount", "Description", "Period"],
                      [12, 14, 16, 24, 12, 12, 20, 17, 28, 14, 30, 10], rows)


def _fmt_date(raw):
    """Render a txn_date (stored as ``YYYY-MM-DD`` ISO string) as
    ``DD-Mon-YYYY`` for readability — falls back to whatever's in the
    field if we can't parse it."""
    if not raw:
        return ""
    try:
        return _dt.date.fromisoformat(str(raw)[:10]).strftime("%d-%b-%Y")
    except (ValueError, TypeError):
        return str(raw)


def _sheet_reimbursements(wb, data: MISData, lbl: dict,
                            suffix: str = "") -> None:
    """Per-row reimbursement detail. One row per uploaded entry.

    Columns: Period | Date | CostCentre | Employee | Client |
             Client Reimbursable | Amount

    Cost centre comes from the client master (the partner serving
    that client). The Client column shows the resolved master name
    or the raw text + a "unmapped" hint if the client_raw hasn't
    been linked yet.

    Cost Centre P&L SUMIFs against this sheet's Amount column (G)
    via CostCentre (C) so the partner-level totals include
    reimbursements.
    """
    def _client_label(f):
        cid = f.get("client_id")
        if cid is not None:
            return lbl["cli"].get(cid, "(unmapped)")
        raw = f.get("client_raw")
        if raw:
            return f"{raw}  ← unmapped, link in Review tab"
        return "(no client)"
    rows = [[
        f["period"], _fmt_date(f.get("txn_date")),
        lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
        f["employee_name"], _client_label(f),
        "Yes" if f["client_reimbursable"] else "No",
        round(f["amount"], 2),
    ] for f in data.reimbursement_facts]
    _write_data_sheet(
        wb, "Reimbursements" + suffix,
        ["Period", "Date", "CostCentre", "Employee", "Client",
         "Client Reimbursable", "Amount"],
        [10, 12, 12, 26, 28, 16, 14], rows)


def _sheet_salary(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    def _client_label(f):
        # Distinct labels for residual vs unresolved-timesheet vs resolved.
        if f.get("is_overhead_offset"):
            return "(office indirect expenses allocated to employees)"
        if f.get("is_overhead"):
            return "(office overhead per active employee)"
        if f.get("is_residual"):
            return "(residual / unallocated time)"
        cid = f.get("client_id")
        if cid is not None:
            return lbl["cli"].get(cid, "(unmapped)")
        raw = f.get("client_raw")
        if raw:
            return f"{raw}  ← unmapped, link in Review tab"
        return "(no client)"
    # Column layout (v0.3.68 — three CC columns for clarity):
    #   A Period         B Date           C Charged To      D Employee
    #   E Client         F Client CC      G Home CC         H Hours
    #   I Amount         J Type
    #
    # "Charged To" (was "CostCentre" pre-v0.3.68) = where the cost
    # actually lands. SUMIFS in Cost Centre P&L / Partner-Manager P&L
    # uses this column (still at C) so existing formulas keep working;
    # the rename is header-only.
    # "Client CC" — the CC the worked-on client belongs to; blank for
    # residual / non-billable / overhead rows. Helps the operator see
    # WHY a billable slice was charged to a partner other than the
    # employee's home.
    # "Home CC" — the employee's home CC from the master. Always
    # populated. Lets the operator read the salary bifurcation at a
    # glance: an employee whose Home CC differs from Charged To has
    # worked on a client belonging to another partner.
    # Type — "Salary" or "Overhead"; SUMIFS uses this (now at J) to
    # split Salary Cost from Allocated Overhead.
    #
    # Overhead amounts are LIVE formulas chaining to the Employee
    # Register sheet (per-employee share = office indirect pool ÷
    # active count), so tweaking an office expense row recomputes the
    # whole overhead cascade. The comparison-period sheet keeps plain
    # values — its Employee Register isn't part of the workbook.
    def _cc_label(cc_id):
        if cc_id is None:
            return ""
        return lbl["cc"].get(cc_id, "")
    er = _q("Employee Register")
    live = (suffix == "")

    def _amount(f, r):
        if live and f.get("is_overhead_offset"):
            # −(per-employee share × active count) — backs the allocated
            # pool out of Office.
            return (f"=-SUMIFS({er}!$G:$G,{er}!$A:$A,$A{r})"
                    f"*SUMIFS({er}!$C:$C,{er}!$A:$A,$A{r})")
        if live and f.get("is_overhead"):
            return f"=SUMIFS({er}!$G:$G,{er}!$A:$A,$A{r})"
        return round(f["amount"], 2)

    rows = [[f["period"], _fmt_date(f.get("txn_date")),
             _cc_label(f["cost_centre_id"]) or "Unassigned",
             f["employee_name"], _client_label(f),
             _cc_label(f.get("client_cost_centre_id")),
             _cc_label(f.get("home_cost_centre_id")),
             round(f["hours"], 2), _amount(f, i + 2),
             "Overhead" if f.get("is_overhead") else "Salary"]
            for i, f in enumerate(data.labour_facts)]
    _write_data_sheet(wb, "Salary" + suffix,
                      ["Period", "Date", "Charged To", "Employee", "Client",
                       "Client CC", "Home CC", "Hours", "Amount", "Type"],
                      [10, 12, 12, 26, 28, 12, 12, 12, 14, 12], rows)


# --- Employee Register --------------------------------------------------------

def _sheet_employee_register(wb: Workbook, data: MISData, lbl: dict) -> None:
    """Active headcount per period + joiners/exits, and the office-overhead
    computation the Salary sheet's Overhead rows chain to.

    Three blocks, all formula-driven off the roster table:

    1. **Summary** — one row per period: active employees, new joiners,
       exits (COUNTIFS over the roster), the office indirect pool
       (SUMIFS over the Expenses sheet) and the per-employee overhead
       (pool ÷ active). The Salary sheet's Overhead rows SUMIFS into
       column G here, so the whole overhead cascade is live.
    2. **Roster** — one row per (period, employee): home cost centre,
       Active/Exited status, and the movement vs the previous month.
       "Active" = filed timesheet hours in the period. Exited = was in
       the previous month's timesheet, absent this month.
    3. **Headcount by cost centre** — COUNTIFS per (CC, period).
    """
    reg = data.employee_register
    if not reg:
        return
    ws = wb.create_sheet("Employee Register")
    ws.sheet_view.showGridLines = False
    for col, w in (("A", 12), ("B", 26), ("C", 18), ("D", 13), ("E", 13),
                   ("F", 20), ("G", 22)):
        ws.column_dimensions[col].width = w

    office_code = next(
        (c["code"] for c in lbl["cc_active"] if c["cc_type"] == "office"),
        "Office")
    exp = _q("Expenses")

    _cell(ws, 1, 1, "Employee Register", font=_TITLE)
    _cell(ws, 2, 1,
          "Active = filed timesheet hours in the period (21st → 20th "
          "cycle). Movement compares against the previous month's "
          "timesheet. Office overhead = Office-cost-centre indirect "
          "expenses ÷ active employees — the Salary sheet's Overhead "
          "rows read the per-employee figure from column G.", font=_SUB)

    # ---- Pre-compute the roster rows so the summary COUNTIFS know
    # their range before being written.
    roster_rows: list[list] = []
    for r in reg:
        for emp in r["active"]:
            roster_rows.append([
                r["period"], emp["name"], emp["cc_code"], "Active",
                "New Joiner" if emp["is_new"] else ""])
        for emp in r["exits"]:
            roster_rows.append([
                r["period"], emp["name"], emp["cc_code"], "Exited", "Exit"])

    sum_hrow = 4
    sum_first = sum_hrow + 1
    sum_last = sum_first + len(reg) - 1
    roster_hrow = sum_last + 2
    roster_first = roster_hrow + 1
    roster_last = max(roster_first, roster_first + len(roster_rows) - 1)
    rA = f"$A${roster_first}:$A${roster_last}"
    rC = f"$C${roster_first}:$C${roster_last}"
    rD = f"$D${roster_first}:$D${roster_last}"
    rE = f"$E${roster_first}:$E${roster_last}"

    # ---- 1. Summary -----------------------------------------------------
    _header_row(ws, sum_hrow, [
        "Period", "Prev Month", "Active Employees", "New Joiners", "Exits",
        "Office Indirect (₹)", "Overhead / Employee (₹)"])
    notes = []
    for i, r in enumerate(reg):
        row = sum_first + i
        _cell(ws, row, 1, r["period"], border=True)
        _cell(ws, row, 2, r["prev_period"]
              + ("" if r["has_prev_data"] else "  (no data)"), border=True)
        _cell(ws, row, 3,
              f'=COUNTIFS({rA},$A{row},{rD},"Active")',
              font=_BOLD, border=True, align=_CENTER)
        _cell(ws, row, 4,
              f'=COUNTIFS({rA},$A{row},{rE},"New Joiner")',
              border=True, align=_CENTER)
        _cell(ws, row, 5,
              f'=COUNTIFS({rA},$A{row},{rE},"Exit")',
              border=True, align=_CENTER)
        _cell(ws, row, 6,
              f'=SUMIFS({exp}!$J:$J,{exp}!$E:$E,"{office_code}",'
              f'{exp}!$H:$H,"{EXPENSE_TYPE_INDIRECT}",{exp}!$L:$L,$A{row})',
              fmt=INR, border=True)
        _cell(ws, row, 7,
              f"=IF(C{row}=0,0,IF(F{row}<=0,0,ROUND(F{row}/C{row},2)))",
              font=_BOLD, fmt=INR, border=True)
        if not r["has_prev_data"]:
            notes.append(
                f"{r['period']}: no timesheet found for {r['prev_period']} — "
                f"joiners/exits not computed for this period.")

    # ---- 2. Roster -------------------------------------------------------
    _header_row(ws, roster_hrow, [
        "Period", "Employee", "Home CC", "Status", "Movement"])
    for i, row_vals in enumerate(roster_rows):
        row = roster_first + i
        for ci, val in enumerate(row_vals, start=1):
            _cell(ws, row, ci, val, border=True,
                  align=_CENTER if ci in (1, 3, 4, 5) else None)

    # ---- 3. Headcount by cost centre -------------------------------------
    # Placed BESIDE the summary (top-right, starting at column I) rather
    # than at the bottom of the sheet, so the operator reads both summary
    # tables at a glance without scrolling past the full roster.
    cc_codes: list[str] = []
    for rr in roster_rows:
        if rr[2] not in cc_codes:
            cc_codes.append(rr[2])
    cc_codes.sort()
    if cc_codes:
        hc_c0 = 9                                # column I (one gap after G)
        ccL = get_column_letter(hc_c0)           # Cost Centre column
        perL = get_column_letter(hc_c0 + 1)      # Period column
        for off, w in enumerate((20, 12, 10, 13, 10)):
            ws.column_dimensions[get_column_letter(hc_c0 + off)].width = w
        _cell(ws, sum_hrow - 1, hc_c0, "Headcount by cost centre", font=_BOLD)
        _header_row(ws, sum_hrow, [
            "Cost Centre", "Period", "Active", "New Joiners", "Exits"],
            start_col=hc_c0)
        row = sum_hrow + 1
        for code in cc_codes:
            for r in reg:
                _cell(ws, row, hc_c0, code, border=True)
                _cell(ws, row, hc_c0 + 1, r["period"], border=True,
                      align=_CENTER)
                _cell(ws, row, hc_c0 + 2,
                      f'=COUNTIFS({rA},${perL}{row},{rC},${ccL}{row},'
                      f'{rD},"Active")',
                      border=True, align=_CENTER)
                _cell(ws, row, hc_c0 + 3,
                      f'=COUNTIFS({rA},${perL}{row},{rC},${ccL}{row},'
                      f'{rE},"New Joiner")',
                      border=True, align=_CENTER)
                _cell(ws, row, hc_c0 + 4,
                      f'=COUNTIFS({rA},${perL}{row},{rC},${ccL}{row},'
                      f'{rE},"Exit")',
                      border=True, align=_CENTER)
                row += 1

    for i, note in enumerate(notes):
        _cell(ws, roster_last + 2 + i, 1, "• " + note, font=_SUB)

    ws.freeze_panes = f"A{sum_first}"


# --- Comparatives ------------------------------------------------------------

def _sheet_comparatives(wb: Workbook, data: MISData, compare: MISData,
                        lbl: dict, rows_pl: dict) -> None:
    """Current vs comparison period — revenue & profit per cost centre.

    Current figures link to the Cost Centre P&L sheet; comparison figures are
    SUMIFS over the comparison data sheets — so the whole sheet is live."""
    ws = wb.create_sheet("Comparatives")
    ws.sheet_view.showGridLines = False
    cur_lbl = ", ".join(data.options.periods)
    cmp_lbl = ", ".join(compare.options.periods)
    headers = ["Code", "Cost Centre",
               f"Revenue — {cur_lbl}", f"Revenue — {cmp_lbl}", "Revenue Δ",
               f"Profit — {cur_lbl}", f"Profit — {cmp_lbl}", "Profit Δ",
               "Profit Δ %"]
    for i, w in enumerate([10, 24, 18, 18, 16, 18, 18, 16, 11]):
        ws.column_dimensions[get_column_letter(1 + i)].width = w

    _cell(ws, 1, 1, "Period Comparison", font=_TITLE)
    _cell(ws, 2, 1, f"Current: {cur_lbl}    vs    Comparison: {cmp_lbl}",
          font=_SUB)
    hrow = 4
    _header_row(ws, hrow, headers)

    pl = _q("Cost Centre P&L")
    rev_c = _q("Revenue" + CMP)
    exp_c = _q("Expenses" + CMP)
    lab_c = _q("Salary" + CMP)
    first = hrow + 1
    r = first
    for code, plrow in rows_pl["row_of"].items():
        name_cell = f"{pl}!B{plrow}"
        _cell(ws, r, 1, code, border=True)
        _cell(ws, r, 2, f"={name_cell}", border=True)
        _cell(ws, r, 3, f"={pl}!C{plrow}", fmt=INR, border=True)
        _cell(ws, r, 4, f"=SUMIFS({rev_c}!$H:$H,{rev_c}!$D:$D,$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 5, f"=C{r}-D{r}", fmt=INR, border=True)
        _cell(ws, r, 6, f"={pl}!H{plrow}", fmt=INR, border=True)
        # Comparison profit = comp revenue − comp direct − comp labour
        # (labour includes the Overhead-type rows, which carry the
        # per-employee office allocation + the Office offset, so the
        # per-CC net comes out right). Expenses layout v0.3.69:
        # Amount=J, CostCentre=E.
        _cell(ws, r, 7,
              f"=D{r}-SUMIFS({exp_c}!$J:$J,{exp_c}!$E:$E,$A{r})"
              f"-SUMIFS({lab_c}!$I:$I,{lab_c}!$C:$C,$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 8, f"=F{r}-G{r}", fmt=INR, border=True)
        _cell(ws, r, 9, f"=IF(G{r}=0,\"\",(F{r}-G{r})/ABS(G{r}))",
              fmt=PCT, border=True, align=_CENTER)
        r += 1

    last = r - 1
    _cell(ws, r, 2, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
    for col in (3, 4, 5, 6, 7, 8):
        L = get_column_letter(col)
        _cell(ws, r, col, f"=SUM({L}{first}:{L}{last})", font=_BOLD,
              fill=_TOTAL_FILL, fmt=INR, border=True)
    _cell(ws, r, 9, f"=IF(G{r}=0,\"\",(F{r}-G{r})/ABS(G{r}))", font=_BOLD,
          fill=_TOTAL_FILL, fmt=PCT, border=True, align=_CENTER)
