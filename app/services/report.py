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
from .calc import MISData, OVERHEAD_EQUAL, OVERHEAD_REVENUE

# --- palette & formats -------------------------------------------------------

NAVY = "1F2A44"
BLUE = "2F7DF6"
LIGHT = "EAF0FB"
GREY = "F0F1F4"
# Indian-grouped: lakh/crore style with literal commas (escape commas with \).
# Two-condition format covers up to ~10000 crore on either side.
INR = (r'[<=-100000][Red]-##\,##\,##\,##\,##0;'
       r'[>=100000]##\,##\,##\,##\,##0;'
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
_TOTAL_FILL = PatternFill("solid", fgColor=LIGHT)
_KPI_FILL = PatternFill("solid", fgColor=GREY)
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
    rows_pl = _sheet_cost_centre(wb, data, lbl)
    _sheet_partner_manager(wb, data, lbl)
    _sheet_entity(wb, data, lbl)
    _sheet_service(wb, data, lbl)
    if compare is not None:
        _sheet_comparatives(wb, data, compare, lbl, rows_pl)
    _sheet_revenue(wb, data, lbl)
    _sheet_expenses(wb, data, lbl)
    _sheet_labour(wb, data, lbl)
    if compare is not None:
        _sheet_revenue(wb, compare, lbl, CMP)
        _sheet_expenses(wb, compare, lbl, CMP)
        _sheet_labour(wb, compare, lbl, CMP)

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
        ("Office expense treatment", data.options.overhead_mode.capitalize()),
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


# --- Cost Centre P&L (the core sheet) ----------------------------------------

def _sheet_cost_centre(wb: Workbook, data: MISData, lbl: dict) -> dict:
    ws = wb.create_sheet("Cost Centre P&L")
    ws.sheet_view.showGridLines = False
    headers = ["Code", "Cost Centre", "Revenue", "Direct Expense",
               "Labour Cost", "Allocated Overhead", "Total Cost", "Profit",
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
    lab = _q("Labour")
    first = hrow + 1
    n_partners = len(partners)
    # Row order: partners, then Office, then (optional) Unassigned.
    n = n_partners + len(office) + (1 if has_unassigned else 0)
    last = first + n - 1
    total_row = last + 1
    office_row = first + n_partners if office else None

    mode = data.options.overhead_mode

    def write_row(r, code, name, target, kind):
        _cell(ws, r, 1, code, font=_NORMAL, border=True)
        _cell(ws, r, 2, name, font=_NORMAL, border=True)
        _cell(ws, r, 3, f"=SUMIFS({rev}!$G:$G,{rev}!$C:$C,$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 4, f"=SUMIFS({exp}!$F:$F,{exp}!$C:$C,$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 5, f"=SUMIFS({lab}!$F:$F,{lab}!$B:$B,$A{r})",
              fmt=INR, border=True)
        # Allocated overhead (col F).
        _cell(ws, r, 6, _overhead_formula(r, kind, office_row, first,
                                          n_partners, mode),
              fmt=INR, border=True)
        _cell(ws, r, 7, f"=D{r}+E{r}+F{r}", fmt=INR, border=True, font=_NORMAL)
        _cell(ws, r, 8, f"=C{r}-G{r}", fmt=INR, border=True)
        _cell(ws, r, 9, target or 0, fmt=INR, border=True)
        _cell(ws, r, 10, f"=H{r}-I{r}", fmt=INR, border=True)
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


def _overhead_formula(r, kind, office_row, first, n_partners, mode) -> str:
    """The Allocated-Overhead cell formula for a cost-centre row.

    *kind* is 'partner', 'office' or 'unassigned'. Overhead is spread only
    across partner cost centres; Office carries the offsetting negative.
    """
    if mode not in (OVERHEAD_REVENUE, OVERHEAD_EQUAL) or office_row is None \
            or n_partners <= 0:
        return 0
    office_cost = f"($D${office_row}+$E${office_row})"
    if kind == "office":
        return f"=-({office_cost})"
    if kind != "partner":
        return 0
    if mode == OVERHEAD_EQUAL:
        return f"={office_cost}/{n_partners}"
    # Revenue-share across partner rows; fall back to equal split when there
    # is no revenue (mirrors the calculation engine).
    rev_range = f"$C${first}:$C${first + n_partners - 1}"
    return (f"=IF(SUM({rev_range})=0,{office_cost}/{n_partners},"
            f"{office_cost}*$C{r}/SUM({rev_range}))")


# --- Partner – Manager P&L ---------------------------------------------------

def _sheet_partner_manager(wb: Workbook, data: MISData, lbl: dict) -> None:
    ws = wb.create_sheet("Partner-Manager P&L")
    ws.sheet_view.showGridLines = False
    headers = ["CC", "Mgr", "Partner – Manager", "Revenue",
               "Direct Expense", "Contribution"]
    for i, w in enumerate([8, 8, 26, 16, 16, 16]):
        ws.column_dimensions[get_column_letter(1 + i)].width = w
    _cell(ws, 1, 1, "Partner – Manager Profitability", font=_TITLE)
    hrow = 3
    _header_row(ws, hrow, headers)

    rev, exp = _q("Revenue"), _q("Expenses")
    r = hrow + 1
    first = r
    for pm in data.partner_manager:
        cc = lbl["cc"].get(pm["cost_centre_id"], "Unassigned")
        mg = lbl["mgr"].get(pm["manager_id"], "(unassigned)")
        _cell(ws, r, 1, cc, border=True)
        _cell(ws, r, 2, mg, border=True)
        _cell(ws, r, 3, pm["label"], border=True)
        _cell(ws, r, 4, f"=SUMIFS({rev}!$G:$G,{rev}!$C:$C,$A{r},"
              f"{rev}!$D:$D,$B{r})", fmt=INR, border=True)
        _cell(ws, r, 5, f"=SUMIFS({exp}!$F:$F,{exp}!$C:$C,$A{r},"
              f"{exp}!$D:$D,$B{r})", fmt=INR, border=True)
        _cell(ws, r, 6, f"=D{r}-E{r}", fmt=INR, border=True)
        r += 1
    if r > first:
        _cell(ws, r, 3, "TOTAL", font=_BOLD, fill=_TOTAL_FILL, border=True)
        for col in (4, 5, 6):
            L = get_column_letter(col)
            _cell(ws, r, col, f"=SUM({L}{first}:{L}{r - 1})", font=_BOLD,
                  fill=_TOTAL_FILL, fmt=INR, border=True)
    _cell(ws, r + 2, 1,
          "Note: labour cost is allocated by cost centre, not by manager.",
          font=_SUB)


# --- Entity & Service --------------------------------------------------------

def _sheet_entity(wb: Workbook, data: MISData, lbl: dict) -> None:
    _simple_summary(wb, "Entity P&L", "Entity-wise Profitability",
                    "Entity", data.entities, "ent", lbl, key="name",
                    sumcol_rev="B", sumcol_exp="B")


def _sheet_service(wb: Workbook, data: MISData, lbl: dict) -> None:
    _simple_summary(wb, "Service MIS", "Service-wise Revenue & Cost",
                    "Service", data.services, "svc", lbl, key="name",
                    sumcol_rev="E", sumcol_exp="E")


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
        _cell(ws, r, 2, f"=SUMIFS({rev}!$G:$G,{rev}!${sumcol_rev}:${sumcol_rev},$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 3, f"=SUMIFS({exp}!$F:$F,{exp}!${sumcol_exp}:${sumcol_exp},$A{r})",
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
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    return ws


def _sheet_revenue(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    rows = [[f["period"], lbl["ent"].get(f["entity_id"], "(unspecified)"),
             lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
             lbl["mgr"].get(f["manager_id"], "(unassigned)"),
             lbl["svc"].get(f["service_id"], "(unspecified)"),
             lbl["cli"].get(f["client_id"], "(unmapped)"),
             round(f["amount"], 2)]
            for f in data.revenue_facts]
    _write_data_sheet(wb, "Revenue" + suffix,
                      ["Period", "Entity", "CostCentre", "Manager", "Service",
                       "Client", "Amount"], [10, 24, 12, 12, 20, 28, 14], rows)


def _sheet_expenses(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    rows = [[f["period"], lbl["ent"].get(f["entity_id"], "(unspecified)"),
             lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
             lbl["mgr"].get(f["manager_id"], "(unassigned)"),
             lbl["svc"].get(f["service_id"], "(unspecified)"),
             round(f["amount"], 2), f.get("description", "")]
            for f in data.expense_facts]
    _write_data_sheet(wb, "Expenses" + suffix,
                      ["Period", "Entity", "CostCentre", "Manager", "Service",
                       "Amount", "Description"], [10, 24, 12, 12, 20, 14, 34],
                      rows)


def _sheet_labour(wb, data: MISData, lbl: dict, suffix: str = "") -> None:
    rows = [[f["period"], lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
             f["employee_name"], lbl["cli"].get(f["client_id"], "(unmapped)"),
             round(f["hours"], 2), round(f["amount"], 2)]
            for f in data.labour_facts]
    _write_data_sheet(wb, "Labour" + suffix,
                      ["Period", "CostCentre", "Employee", "Client", "Hours",
                       "Amount"], [10, 12, 26, 28, 12, 14], rows)


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
    lab_c = _q("Labour" + CMP)
    first = hrow + 1
    r = first
    for code, plrow in rows_pl["row_of"].items():
        name_cell = f"{pl}!B{plrow}"
        _cell(ws, r, 1, code, border=True)
        _cell(ws, r, 2, f"={name_cell}", border=True)
        _cell(ws, r, 3, f"={pl}!C{plrow}", fmt=INR, border=True)
        _cell(ws, r, 4, f"=SUMIFS({rev_c}!$G:$G,{rev_c}!$C:$C,$A{r})",
              fmt=INR, border=True)
        _cell(ws, r, 5, f"=C{r}-D{r}", fmt=INR, border=True)
        _cell(ws, r, 6, f"={pl}!H{plrow}", fmt=INR, border=True)
        # Comparison profit = comp revenue − comp direct − comp labour.
        _cell(ws, r, 7,
              f"=D{r}-SUMIFS({exp_c}!$F:$F,{exp_c}!$C:$C,$A{r})"
              f"-SUMIFS({lab_c}!$F:$F,{lab_c}!$B:$B,$A{r})",
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
