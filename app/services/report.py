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
from .calc import MISData, OVERHEAD_EQUAL, OVERHEAD_REVENUE, financial_year

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
    rev, exp, lab = _q("Revenue"), _q("Expenses"), _q("Labour")

    # Returns the SUMIFS formula for a (partner, manager) cell on a given
    # data sheet's amount column.
    def sumifs(sheet_q, amount_col, cc_code, mgr_filter, extra=None):
        parts = [
            f"{sheet_q}!${amount_col}:${amount_col}",
            f"{sheet_q}!$C:$C", f'"{cc_code}"',
        ]
        if mgr_filter is not None:
            parts.append(f"{sheet_q}!$D:$D")
            parts.append(f'"{mgr_filter}"')
        for col, value in (extra or []):
            parts.append(f"{sheet_q}!${col}:${col}")
            parts.append(f'"{value}"')
        return "=SUMIFS(" + ",".join(parts) + ")"

    def labour_sumifs(cc_code):
        # Labour facts don't carry a manager, so cells under a manager column
        # just read the partner-level labour cost. We attribute it to the
        # partner's "Self" (first) column only, leaving manager columns at 0.
        return f"=SUMIFS({lab}!$F:$F,{lab}!$B:$B,\"{cc_code}\")"

    # Row layout. Each entry: (label, kind, params)
    # kinds:
    #   "sales"     -> Revenue, Category != Reimbursement / OPE
    #   "reimb"     -> Revenue, Category IN (Reimbursement, OPE)
    #   "salary"    -> Labour amount (partner-level only)
    #   "expense"   -> Expenses
    #   "income_sum"-> SUM of sales + reimb rows
    #   "cost_sum"  -> SUM of salary + expense rows
    #   "gross"     -> income_sum - cost_sum
    #   "gross_pct" -> gross / income
    #   "net"       -> gross   (until office overhead is added)
    #   "net_pct"   -> net / income
    #   "section"   -> bold label spanning a row
    # We track by row number for cross-referencing.
    # Allocated overhead per partner (computed by calc engine; depends on the
    # operator's overhead-allocation mode). Written into the Total column of
    # the "Office Overhead" row.
    overhead_by_code = {c.code: c.allocated_overhead
                         for c in data.cost_centres if not c.is_office}

    plan = [
        ("Sales (Income)", "sales"),
        ("Reimbursement & OPE", "reimb"),
        ("Total Income", "income_sum"),
        ("", "blank"),
        ("Salary (labour cost)", "salary"),
        ("Other Direct Expenses", "expense"),
        ("Total Direct Costs", "cost_sum"),
        ("", "blank"),
        ("Gross Profit", "gross"),
        ("Gross Profit %", "gross_pct"),
        ("", "blank"),
        ("Office Overhead (allocated)", "overhead"),
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
                    # manager-level — write the value into the Total column.
                    formula = round(overhead_by_code.get(cc_code, 0.0), 2)
                elif is_total_col and kind == "net":
                    gross_r = rows_by_kind["gross"]
                    overhead_r = rows_by_kind["overhead"]
                    L = get_column_letter(col)
                    formula = f"={L}{gross_r}-{L}{overhead_r}"
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
                    formula = sumifs(rev, "G", cc_code, mgr_filter,
                                     extra=[("H", "Income")])
                elif kind == "reimb":
                    # Reimbursement + OPE together — two SUMIFS summed.
                    f1 = sumifs(rev, "G", cc_code, mgr_filter,
                                extra=[("H", "Reimbursement")])
                    f2 = sumifs(rev, "G", cc_code, mgr_filter,
                                extra=[("H", "OPE")])
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
                    formula = sumifs(exp, "F", cc_code, mgr_filter)
                elif kind == "cost_sum":
                    sal_r = rows_by_kind["salary"]
                    exp_r = rows_by_kind["expense"]
                    formula = (f"={get_column_letter(col)}{sal_r}+"
                               f"{get_column_letter(col)}{exp_r}")
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
          "Labour is allocated to the partner cost-centre (not split by "
          "manager); other expenses follow the Cost Center column on the "
          "voucher split.", font=_SUB)


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
    rows = []
    for f in data.revenue_facts:
        svc_name = lbl["svc"].get(f["service_id"], "(unspecified)")
        rows.append([
            f["period"],
            lbl["ent"].get(f["entity_id"], "(unspecified)"),
            lbl["cc"].get(f["cost_centre_id"], "Unassigned"),
            lbl["mgr"].get(f["manager_id"], "(unassigned)"),
            svc_name,
            lbl["cli"].get(f["client_id"], "(unmapped)"),
            round(f["amount"], 2),
            _service_category(svc_name),
        ])
    _write_data_sheet(
        wb, "Revenue" + suffix,
        ["Period", "Entity", "CostCentre", "Manager", "Service",
         "Client", "Amount", "Category"],
        [10, 24, 12, 12, 22, 28, 14, 14], rows)


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
