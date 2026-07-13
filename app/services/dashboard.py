"""Interactive HTML dashboard generated alongside the Excel MIS.

Single source of truth: this renders from the SAME :class:`MISData` the
Excel workbook is built from (plus the shared :func:`report.budget_monthly_data`
for the FY-to-date budget view), so every figure on the dashboard ties to
the workbook exactly — there is no second calculation path.

The output is a self-contained ``.html`` file: Chart.js is inlined (the
vendored copy under ``app/assets``; CDN only as a fallback), tables are
rendered server-side, and money is formatted with the same Indian
lakh/crore grouping (:func:`app.util.fmt_inr`) as the workbook. It opens
in any browser with no internet and nothing to install — board-room ready.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
from pathlib import Path

from .. import config
from ..util import fmt_inr
from .calc import MISData
from .resolution import norm
from . import report

# Categorical palette (firm blue first), reused for partners / services / etc.
_PALETTE = [
    "#2F7DF6", "#16A34A", "#F59E0B", "#DC2626", "#7C3AED", "#0891B2",
    "#DB2777", "#65A30D", "#EA580C", "#0EA5E9", "#9333EA", "#14B8A6",
    "#F43F5E", "#84CC16", "#6366F1", "#CA8A04",
]


def _money(v) -> str:
    return "₹" + fmt_inr(v)


def _pct(num: float, den: float) -> str:
    return f"{(num / den * 100):.1f}%" if den else "—"


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


# --- small HTML builders -----------------------------------------------------

def _kpi_card(label: str, value: str, accent: str, sub: str = "") -> str:
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    return (f"<div class='kpi' style='--accent:{accent}'>"
            f"<div class='kpi-label'>{_esc(label)}</div>"
            f"<div class='kpi-value'>{value}</div>{sub_html}</div>")


_table_seq = 0


def _table(headers: list[str], rows: list[list[str]], right_cols: set[int],
           total_row: list[str] | None = None,
           searchable: bool | None = None) -> str:
    """Sortable table. Click a header to sort (numeric columns sort by
    value, parsed from the formatted text; the TOTAL row stays pinned).
    Long tables (or ``searchable=True``) also get a filter box."""
    global _table_seq
    _table_seq += 1
    tid = f"tbl{_table_seq}"
    if searchable is None:
        searchable = len(rows) > 10
    th = "".join(
        f"<th class='{'num' if i in right_cols else ''}'>{_esc(h)}</th>"
        for i, h in enumerate(headers))
    body = []
    for row in rows:
        tds = "".join(
            f"<td class='{'num' if i in right_cols else ''}'>{c}</td>"
            for i, c in enumerate(row))
        body.append(f"<tr>{tds}</tr>")
    if total_row is not None:
        tds = "".join(
            f"<td class='{'num' if i in right_cols else ''}'>{c}</td>"
            for i, c in enumerate(total_row))
        body.append(f"<tr class='total'>{tds}</tr>")
    search = (f"<input class='tbl-search' data-target='{tid}' "
              f"oninput='filterTable(this)' placeholder='Filter rows…'>"
              if searchable else "")
    return (f"{search}<div class='table-wrap'>"
            f"<table id='{tid}' class='sortable'><thead><tr>{th}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></div>")


class _Charts:
    """Collects ``<canvas>`` placeholders + the JS calls that fill them."""

    def __init__(self) -> None:
        self._js: list[str] = []
        self._n = 0

    def _canvas(self, height: int = 340):
        self._n += 1
        cid = f"chart{self._n}"
        return cid, (f"<div class='chart-box' style='height:{height}px'>"
                     f"<canvas id='{cid}'></canvas></div>")

    @staticmethod
    def _toolbar(cid: str, default_top: str = "all",
                 default_sort: str = "default") -> str:
        """Sort + Top-N controls bound to one chart (wired to applyControls)."""
        def opt(value, text, current):
            sel = " selected" if value == current else ""
            return f"<option value='{value}'{sel}>{text}</option>"
        sort_opts = "".join([
            opt("default", "Default", default_sort),
            opt("valDesc", "Value ↓", default_sort),
            opt("valAsc", "Value ↑", default_sort),
            opt("nameAsc", "Name A–Z", default_sort),
            opt("nameDesc", "Name Z–A", default_sort)])
        top_opts = "".join([
            opt("all", "All", default_top), opt("5", "Top 5", default_top),
            opt("10", "Top 10", default_top), opt("15", "Top 15", default_top),
            opt("20", "Top 20", default_top), opt("30", "Top 30", default_top)])
        return (
            f"<div class='chart-tools'>"
            f"<label>Sort <select data-ctrl='sort' data-target='{cid}' "
            f"onchange=\"applyControls('{cid}')\">{sort_opts}</select></label>"
            f"<label>Show <select data-ctrl='top' data-target='{cid}' "
            f"onchange=\"applyControls('{cid}')\">{top_opts}</select></label>"
            f"</div>")

    def grouped_bar(self, labels, datasets, unit="money", height=340,
                    horizontal=False, stacked=False, controls=False,
                    default_top="all") -> str:
        cid, box = self._canvas(height)
        self._js.append(
            f"groupedBar('{cid}', {json.dumps(labels)}, "
            f"{json.dumps(datasets)}, '{unit}', {str(horizontal).lower()}, "
            f"{str(stacked).lower()});")
        if controls:
            self._js.append(f"applyControls('{cid}');")
            return self._toolbar(cid, default_top) + box
        return box

    def donut(self, labels, values, height=340, controls=False,
              default_top="all") -> str:
        cid, box = self._canvas(height)
        self._js.append(
            f"donut('{cid}', {json.dumps(labels)}, {json.dumps(values)});")
        if controls:
            self._js.append(f"applyControls('{cid}');")
            return self._toolbar(cid, default_top) + box
        return box

    def line(self, labels, datasets, unit="money", height=340) -> str:
        cid, box = self._canvas(height)
        self._js.append(
            f"lineChart('{cid}', {json.dumps(labels)}, "
            f"{json.dumps(datasets)}, '{unit}');")
        return box

    def script(self) -> str:
        return "\n".join(self._js)


# --- section builders --------------------------------------------------------

def _section(title: str, anchor: str, *blocks: str, intro: str = "") -> str:
    intro_html = f"<p class='sec-intro'>{_esc(intro)}</p>" if intro else ""
    return (f"<section id='{anchor}'><h2>{_esc(title)}</h2>{intro_html}"
            f"{''.join(blocks)}</section>")


def _grid(*items: str) -> str:
    return f"<div class='grid'>{''.join(items)}</div>"


def _card(*inner: str) -> str:
    return f"<div class='card'>{''.join(inner)}</div>"


def _cost_centre_section(data: MISData, ch: _Charts) -> str:
    ccs = data.cost_centres
    partners = [c for c in ccs if not c.is_office and c.cost_centre_id is not None]

    p_labels = [c.code for c in partners]
    rev = [round(c.total_income, 2) for c in partners]   # income + reimb OPE
    cost = [round(c.total_cost, 2) for c in partners]
    profit = [round(c.profit, 2) for c in partners]

    pl_bar = ch.grouped_bar(
        p_labels,
        [{"label": "Revenue", "data": rev},
         {"label": "Total Cost", "data": cost},
         {"label": "Profit", "data": profit}],
        controls=True)

    rev_partners = [(c.code, round(c.total_income, 2)) for c in partners
                    if c.total_income > 0]
    donut = ch.donut([c for c, _ in rev_partners],
                     [v for _, v in rev_partners], controls=True)

    # Cost composition (Direct / Reimbursements / Salary billable / Salary
    # non-billable / Overhead) for every cost centre incl Office. Salary is
    # split the same way the Partner-Manager P&L splits it (v0.3.82).
    bill: dict = {}
    nonbill: dict = {}
    for f in data.labour_facts:
        if f.get("is_overhead"):
            continue
        cc_id = f["cost_centre_id"]
        bucket = bill if f.get("billable") else nonbill
        bucket[cc_id] = bucket.get(cc_id, 0.0) + f["amount"]
    comp_labels = [c.code for c in ccs]
    comp = ch.grouped_bar(
        comp_labels,
        [{"label": "Direct Expense", "data": [round(c.direct_expense, 2) for c in ccs]},
         {"label": "Reimbursements", "data": [round(c.reimbursement_expense, 2) for c in ccs]},
         {"label": "Salary (billable)", "data": [round(bill.get(c.cost_centre_id, 0.0), 2) for c in ccs]},
         {"label": "Salary (non-billable)", "data": [round(nonbill.get(c.cost_centre_id, 0.0), 2) for c in ccs]},
         {"label": "Allocated Overhead", "data": [round(c.allocated_overhead, 2) for c in ccs]}],
        stacked=True)

    # Table mirrors the Excel Cost Centre P&L (v0.3.89): Revenue +
    # Reimbursements (OPE) on the income side; Direct Expense +
    # Reimbursements on the cost side; no Target / Variance.
    headers = ["Code", "Cost Centre", "Revenue", "Reimb. (OPE)",
               "Total Income", "Direct Exp.", "Reimb.", "Salary", "Overhead",
               "Total Cost", "Profit", "Margin"]
    right = set(range(2, 12))
    rows = []
    for c in ccs:
        rows.append([
            _esc(c.code), _esc(c.name), _money(c.revenue),
            _money(c.reimbursement_income), _money(c.total_income),
            _money(c.direct_expense), _money(c.reimbursement_expense),
            _money(c.labour), _money(c.allocated_overhead),
            _money(c.total_cost), _money(c.profit),
            _pct(c.profit, c.revenue)])   # margin on sales income only
    income_total = sum(c.revenue for c in ccs)
    total = ["", "TOTAL", _money(income_total),
             _money(sum(c.reimbursement_income for c in ccs)),
             _money(sum(c.total_income for c in ccs)),
             _money(sum(c.direct_expense for c in ccs)),
             _money(sum(c.reimbursement_expense for c in ccs)),
             _money(sum(c.labour for c in ccs)),
             _money(sum(c.allocated_overhead for c in ccs)),
             _money(data.total_cost), _money(data.total_profit),
             _pct(data.total_profit, income_total)]

    return _section(
        "Cost Centre P&L", "ccpl",
        _grid(_card("<h3>Revenue · Cost · Profit by partner</h3>", pl_bar),
              _card("<h3>Revenue share by partner</h3>", donut)),
        _card("<h3>Cost composition by cost centre</h3>", comp),
        _card("<h3>Full P&L</h3>", _table(headers, rows, right, total)),
        intro="Partner-wise profitability. Income = Revenue + Reimbursements "
              "(OPE); Profit = Income − (Direct Expense + Reimbursements + "
              "Salary + Allocated Overhead).")


def _budget_section(data: MISData, lbl: dict, ch: _Charts) -> str:
    bm = report.budget_monthly_data(data, lbl)
    if bm is None:
        return ""
    months = bm["months"]
    partners = bm["partners"]
    monthly = bm["monthly"]
    budgets = bm["budgets"]
    rem = bm["remaining_months"]
    m_short = [report._month_short(m) for m in months]

    codes = [p["code"] for p in partners]
    ytd = {p["code"]: sum(monthly.get(p["code"], {}).get(m, 0.0) for m in months)
           for p in partners}
    budget_vals = [round(budgets.get(c, 0.0), 2) for c in codes]
    ytd_vals = [round(ytd[c], 2) for c in codes]

    ba_bar = ch.grouped_bar(
        codes,
        [{"label": "Annual Budget", "data": budget_vals},
         {"label": "YTD Sales", "data": ytd_vals}],
        controls=True)

    # Monthly sales trend — one line per partner + a firm total line.
    line_ds = []
    for p in partners:
        line_ds.append({
            "label": p["code"],
            "data": [round(monthly.get(p["code"], {}).get(m, 0.0), 2)
                     for m in months]})
    total_line = [round(sum(monthly.get(p["code"], {}).get(m, 0.0)
                            for p in partners), 2) for m in months]
    line_ds.append({"label": "All partners", "data": total_line})
    trend = ch.line(m_short, line_ds)

    headers = (["Code", "Cost Centre", "Annual Budget"] + m_short
               + ["YTD Total", "Variance vs Budget",
                  f"Avg / Remaining Month ({rem})"])
    right = set(range(2, 3 + len(months) + 3))
    rows = []
    col_tot = {"budget": 0.0, "ytd": 0.0, "months": [0.0] * len(months)}
    for p in partners:
        code = p["code"]
        b = budgets.get(code, 0.0)
        mvals = [monthly.get(code, {}).get(m, 0.0) for m in months]
        y = sum(mvals)
        var = b - y
        avg = (var / rem) if rem else 0.0
        col_tot["budget"] += b
        col_tot["ytd"] += y
        for i, mv in enumerate(mvals):
            col_tot["months"][i] += mv
        rows.append([_esc(code), _esc(p["name"]), _money(b)]
                    + [_money(mv) for mv in mvals]
                    + [_money(y), _money(var), _money(avg)])
    tvar = col_tot["budget"] - col_tot["ytd"]
    total = (["", "TOTAL", _money(col_tot["budget"])]
             + [_money(mv) for mv in col_tot["months"]]
             + [_money(col_tot["ytd"]), _money(tvar),
                _money(tvar / rem if rem else 0.0)])

    return _section(
        "Budget vs Monthly Sales", "budget",
        _grid(_card("<h3>Annual budget vs YTD sales</h3>", ba_bar),
              _card("<h3>Monthly sales trend</h3>", trend)),
        _card("<h3>FY-to-date detail</h3>", _table(headers, rows, right, total)),
        intro=f"FY {bm['fy']} to date. The last column is the average monthly "
              f"sales still needed to hit budget (Variance ÷ {rem} months left).")


def _entity_section(data: MISData, ch: _Charts) -> str:
    ents = [e for e in data.entities if e.get("revenue") or e.get("direct_expense")]
    if not ents:
        return ""
    labels = [e["name"] for e in ents]
    donut = ch.donut([e["name"] for e in ents if e["revenue"] > 0],
                     [round(e["revenue"], 2) for e in ents if e["revenue"] > 0],
                     controls=True)
    bar = ch.grouped_bar(
        labels,
        [{"label": "Revenue", "data": [round(e["revenue"], 2) for e in ents]},
         {"label": "Direct Expense", "data": [round(e["direct_expense"], 2) for e in ents]},
         {"label": "Net", "data": [round(e["revenue"] - e["direct_expense"], 2) for e in ents]}],
        horizontal=True, height=max(240, 60 + 38 * len(ents)), controls=True)
    headers = ["Entity", "Revenue", "Direct Expense", "Net"]
    rows = [[_esc(e["name"]), _money(e["revenue"]),
             _money(e["direct_expense"]),
             _money(e["revenue"] - e["direct_expense"])] for e in ents]
    tr = sum(e["revenue"] for e in ents)
    te = sum(e["direct_expense"] for e in ents)
    total = ["TOTAL", _money(tr), _money(te), _money(tr - te)]
    return _section(
        "Entity P&L", "entity",
        _grid(_card("<h3>Revenue share by entity</h3>", donut),
              _card("<h3>Revenue · Expense · Net</h3>", bar)),
        _card("<h3>By entity</h3>", _table(headers, rows, {1, 2, 3}, total)))


def _service_section(data: MISData, ch: _Charts) -> str:
    svcs = [s for s in data.services if s.get("revenue") or s.get("direct_expense")]
    if not svcs:
        return ""
    rev_svcs = sorted([s for s in svcs if s["revenue"] > 0],
                      key=lambda s: -s["revenue"])
    donut = ch.donut([s["name"] for s in rev_svcs],
                     [round(s["revenue"], 2) for s in rev_svcs], controls=True)
    headers = ["Service", "Revenue", "Direct Expense", "Net"]
    rows = [[_esc(s["name"]), _money(s["revenue"]),
             _money(s["direct_expense"]),
             _money(s["revenue"] - s["direct_expense"])]
            for s in sorted(svcs, key=lambda s: -s["revenue"])]
    tr = sum(s["revenue"] for s in svcs)
    te = sum(s["direct_expense"] for s in svcs)
    total = ["TOTAL", _money(tr), _money(te), _money(tr - te)]
    bar = ch.grouped_bar(
        [s["name"] for s in rev_svcs],
        [{"label": "Revenue", "data": [round(s["revenue"], 2) for s in rev_svcs]}],
        horizontal=True, height=max(240, 60 + 34 * len(rev_svcs)), controls=True)
    return _section(
        "Service MIS", "service",
        _grid(_card("<h3>Revenue share by service</h3>", donut),
              _card("<h3>Revenue by service</h3>", bar)),
        _card("<h3>By service</h3>", _table(headers, rows, {1, 2, 3}, total)))


def _partner_manager_section(data: MISData, ch: _Charts) -> str:
    pm = [d for d in data.partner_manager if d.get("revenue") or d.get("direct_expense")]
    if not pm:
        return ""
    pm_sorted = sorted(pm, key=lambda d: -d["revenue"])
    bar = ch.grouped_bar(
        [d["label"] for d in pm_sorted],
        [{"label": "Revenue", "data": [round(d["revenue"], 2) for d in pm_sorted]},
         {"label": "Direct Expense", "data": [round(d["direct_expense"], 2) for d in pm_sorted]}],
        horizontal=True, height=max(240, 60 + 30 * len(pm_sorted)), controls=True)
    headers = ["Partner – Manager", "Revenue", "Direct Expense", "Net"]
    rows = [[_esc(d["label"]), _money(d["revenue"]),
             _money(d["direct_expense"]),
             _money(d["revenue"] - d["direct_expense"])] for d in pm_sorted]
    tr = sum(d["revenue"] for d in pm)
    te = sum(d["direct_expense"] for d in pm)
    total = ["TOTAL", _money(tr), _money(te), _money(tr - te)]
    return _section(
        "Partner – Manager P&L", "pm",
        _card("<h3>Revenue &amp; direct expense by partner – manager</h3>", bar),
        _card("<h3>Detail</h3>", _table(headers, rows, {1, 2, 3}, total)))


def _client_section(data: MISData, lbl: dict, ch: _Charts) -> str:
    periods = sorted(data.options.periods)
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
        return ""
    rows_data = []
    for key, per in agg.items():
        amounts = [round(per.get(p, 0.0), 2) for p in periods]
        rows_data.append((names[key], round(sum(amounts), 2), amounts))
    rows_data.sort(key=lambda r: -r[1])

    # Pass ALL clients to the chart (already value-desc); the Top-N control
    # defaults to 15 so it opens compact but the user can expand / re-sort.
    shown = min(len(rows_data), 20)
    bar = ch.grouped_bar(
        [r[0] for r in rows_data],
        [{"label": "Billing", "data": [r[1] for r in rows_data]}],
        horizontal=True, height=max(240, 60 + 30 * shown),
        controls=True, default_top="15")

    headers = ["Client", "Grand Total"] + [report._month_short(p) for p in periods]
    right = set(range(1, 2 + len(periods)))
    rows = [[_esc(n), _money(tot)] + [_money(a) for a in amts]
            for n, tot, amts in rows_data]
    col_tot = [sum(r[2][i] for r in rows_data) for i in range(len(periods))]
    grand = sum(r[1] for r in rows_data)
    total = ["TOTAL", _money(grand)] + [_money(v) for v in col_tot]
    note = ("Chart shows the top 15 by default — use “Show” to see more; "
            "the table below lists every client."
            if len(rows_data) > 15 else "")
    return _section(
        "Client Billing", "clients",
        _card("<h3>Clients by billing</h3>", bar),
        _card("<h3>All clients</h3>", _table(headers, rows, right, total)),
        intro=note)


def _provision_section(data: MISData, lbl: dict, ch: _Charts) -> str:
    pf = data.provision_facts
    if not pf:
        return ""
    pf = sorted(pf, key=lambda f: -f["amount"])
    bar = ch.grouped_bar(
        [(f.get("client_name") or "(unmapped)") for f in pf],
        [{"label": "Remaining", "data": [round(f["amount"], 2) for f in pf]}],
        horizontal=True, height=max(240, 60 + 30 * min(len(pf), 20)),
        controls=True)
    headers = ["Booked", "Entity", "Cost Centre", "Client",
               "Original", "Adjusted", "Remaining"]
    rows = [[_esc(report._month_short(f["provision_period"])
                  if f.get("provision_period") else ""),
             _esc(f.get("entity_name") or "(unspecified)"),
             _esc(lbl["cc"].get(f["cost_centre_id"], "Unassigned")),
             _esc(f.get("client_name") or "(unmapped)"),
             _money(f.get("original", 0.0)), _money(f.get("adjusted", 0.0)),
             _money(f["amount"])] for f in pf]
    total = ["", "", "", "TOTAL",
             _money(sum(f.get("original", 0.0) for f in pf)),
             _money(sum(f.get("adjusted", 0.0) for f in pf)),
             _money(sum(f["amount"] for f in pf))]
    return _section(
        "Provisions", "provisions",
        _card("<h3>Outstanding provisions by client</h3>", bar),
        _card("<h3>Provision detail</h3>",
              _table(headers, rows, {4, 5, 6}, total)),
        intro="Expected direct costs not yet incurred — carried forward at "
              "their remaining value (original − adjustments) until cleared.")


def _employee_section(data: MISData, ch: _Charts) -> str:
    reg = data.employee_register
    if not reg:
        return ""
    periods = [r["period"] for r in reg]
    p_short = [report._month_short(p) for p in periods]

    head_bar = ch.grouped_bar(
        p_short,
        [{"label": "Active", "data": [r["active_count"] for r in reg]},
         {"label": "New Joiners", "data": [r["new_count"] for r in reg]},
         {"label": "Exits", "data": [r["exit_count"] for r in reg]}],
        unit="count", height=300)

    # Headcount by cost centre, stacked per period. Only CONSIDERED
    # roster members count (v0.3.106) — the register now carries
    # everyone, flagged by the location selection, and the chart must
    # keep tying to the workbook's filtered counts.
    cc_codes: list[str] = []
    for r in reg:
        for emp in r["active"]:
            if emp.get("considered", True) and emp["cc_code"] not in cc_codes:
                cc_codes.append(emp["cc_code"])
    cc_codes.sort()
    cc_ds = []
    for code in cc_codes:
        cc_ds.append({
            "label": code,
            "data": [sum(1 for e in r["active"]
                         if e.get("considered", True)
                         and e["cc_code"] == code)
                     for r in reg]})
    cc_bar = ch.grouped_bar(p_short, cc_ds, unit="count", stacked=True,
                            height=300)

    overhead = ch.line(
        p_short,
        [{"label": "Office indirect pool", "data": [round(r["pool"], 2) for r in reg]},
         {"label": "Overhead / employee", "data": [round(r["per_employee"], 2) for r in reg]}])

    headers = ["Period", "Active", "New Joiners", "Exits",
               "Office Indirect (₹)", "Overhead / Employee (₹)"]
    rows = [[report._month_short(r["period"]), str(r["active_count"]),
             str(r["new_count"]), str(r["exit_count"]),
             _money(r["pool"]), _money(r["per_employee"])] for r in reg]
    return _section(
        "Employee Register", "employees",
        _grid(_card("<h3>Headcount movement by period</h3>", head_bar),
              _card("<h3>Active headcount by cost centre</h3>", cc_bar)),
        _card("<h3>Office overhead</h3>", overhead),
        _card("<h3>By period</h3>", _table(headers, rows, {1, 2, 3, 4, 5})),
        intro="Active = filed timesheet hours in the period. Office overhead "
              "per employee = Office indirect expenses ÷ active employees.")


def _client_register_section(data: MISData, ch: _Charts) -> str:
    reg = data.client_register
    if not reg:
        return ""
    periods = [r["period"] for r in reg]
    p_short = [report._month_short(p) for p in periods]

    move_bar = ch.grouped_bar(
        p_short,
        [{"label": "Active", "data": [r["active_count"] for r in reg]},
         {"label": "New", "data": [r["new_count"] for r in reg]}],
        unit="count", height=300)

    # Active clients by cost centre, stacked per period.
    cc_codes: list[str] = []
    for r in reg:
        for c in r["active"]:
            if c["cc_code"] not in cc_codes:
                cc_codes.append(c["cc_code"])
    cc_codes.sort()
    cc_ds = [{"label": code,
              "data": [sum(1 for c in r["active"] if c["cc_code"] == code)
                       for r in reg]} for code in cc_codes]
    cc_bar = ch.grouped_bar(p_short, cc_ds, unit="count", stacked=True,
                            height=300)

    headers = ["Period", "Active Clients", "New Clients"]
    rows = [[report._month_short(r["period"]), str(r["active_count"]),
             str(r["new_count"])] for r in reg]
    return _section(
        "Client Register", "clientreg",
        _grid(_card("<h3>Active &amp; new clients by period</h3>", move_bar),
              _card("<h3>Active clients by cost centre</h3>", cc_bar)),
        _card("<h3>By period</h3>", _table(headers, rows, {1, 2})),
        intro="Active = billed on a sales voucher in the period. New = billed "
              "for the first time ever (clients bill irregularly, so a "
              "month's absence isn't treated as lost).")


# --- assets ------------------------------------------------------------------

def _chartjs_tag() -> str:
    """Inline the vendored Chart.js so the file works fully offline; fall
    back to the CDN only if the bundled asset can't be read."""
    path = config.resource_path("app", "assets", "chart.umd.min.js")
    try:
        return "<script>" + path.read_text(encoding="utf-8") + "</script>"
    except Exception:                                       # pragma: no cover
        return ('<script src="https://cdn.jsdelivr.net/npm/'
                'chart.js@4.4.9/dist/chart.umd.min.js"></script>')


_CSS = """
:root{--navy:#1F2A44;--blue:#2F7DF6;--ink:#0F172A;--muted:#64748B;
 --line:#E2E8F0;--bg:#F1F5F9;--card:#FFFFFF;}
*{box-sizing:border-box;}
body{margin:0;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
 color:var(--ink);background:var(--bg);-webkit-print-color-adjust:exact;
 print-color-adjust:exact;}
header.top{background:linear-gradient(120deg,#1F2A44,#274472);color:#fff;
 padding:26px 40px;}
header.top h1{margin:0;font-size:24px;font-weight:700;}
header.top .sub{color:#BFD3F5;font-size:14px;margin-top:2px;}
header.top .meta{margin-top:12px;font-size:12.5px;color:#D6E2F7;}
header.top .meta b{color:#fff;}
nav{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid
 var(--line);padding:10px 40px;display:flex;gap:18px;flex-wrap:wrap;
 box-shadow:0 1px 4px rgba(15,23,42,.05);}
nav a{color:var(--muted);text-decoration:none;font-size:13px;font-weight:600;}
nav a:hover{color:var(--blue);}
nav .print{margin-left:auto;border:1px solid var(--line);border-radius:6px;
 padding:4px 12px;cursor:pointer;background:#fff;color:var(--navy);}
main{padding:24px 40px 64px;max-width:1280px;margin:0 auto;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
 gap:16px;margin:8px 0 26px;}
.kpi{background:var(--card);border-radius:12px;padding:16px 18px;
 border-left:5px solid var(--accent);box-shadow:0 1px 3px rgba(15,23,42,.08);}
.kpi-label{font-size:12px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.04em;font-weight:600;}
.kpi-value{font-size:25px;font-weight:700;margin-top:6px;color:var(--navy);}
.kpi-sub{font-size:12px;color:var(--muted);margin-top:4px;}
section{margin:30px 0;}
section h2{font-size:19px;color:var(--navy);margin:0 0 4px;
 border-left:4px solid var(--blue);padding-left:10px;}
.sec-intro{color:var(--muted);font-size:13px;margin:0 0 14px 14px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
@media(max-width:900px){.grid{grid-template-columns:1fr;}}
.card{background:var(--card);border-radius:12px;padding:16px 18px;
 box-shadow:0 1px 3px rgba(15,23,42,.08);margin-bottom:18px;}
.card h3{margin:0 0 12px;font-size:14px;color:var(--navy);font-weight:600;}
.chart-tools{display:flex;gap:14px;justify-content:flex-end;flex-wrap:wrap;
 margin:-4px 0 10px;}
.chart-tools label{font-size:11px;color:var(--muted);font-weight:600;
 display:flex;align-items:center;gap:5px;}
.chart-tools select{font-size:12px;padding:3px 6px;border:1px solid var(--line);
 border-radius:6px;background:#fff;color:var(--ink);cursor:pointer;}
.chart-tools select:hover{border-color:var(--blue);}
@media print{.chart-tools{display:none;}}
.chart-box{position:relative;width:100%;}
table{width:100%;border-collapse:collapse;font-size:12.5px;}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;
 white-space:nowrap;}
th{color:var(--muted);font-weight:600;text-transform:uppercase;
 font-size:11px;letter-spacing:.03em;}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;}
th.th-sort{cursor:pointer;user-select:none;}
th.th-sort:hover{color:var(--blue);}
th.th-sort::after{content:'⇅';opacity:.3;margin-left:5px;font-size:9px;}
th.sorted-asc::after{content:'▲';opacity:.85;}
th.sorted-desc::after{content:'▼';opacity:.85;}
.tbl-search{margin:0 0 10px;padding:6px 10px;border:1px solid var(--line);
 border-radius:6px;font-size:12.5px;width:240px;max-width:100%;}
.tbl-search:focus{outline:none;border-color:var(--blue);}
tbody tr:nth-child(even){background:#F8FAFC;}
tr.total td{font-weight:700;color:var(--navy);border-top:2px solid var(--navy);
 background:#EEF4FF;}
.table-wrap{overflow-x:auto;}
footer{color:var(--muted);font-size:12px;padding:24px 40px;text-align:center;
 border-top:1px solid var(--line);}
.warn{background:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;padding:
 10px 14px;font-size:12.5px;color:#92400E;margin-bottom:16px;}
@media print{nav{position:static;}.card,.kpi{box-shadow:none;
 border:1px solid var(--line);}.tbl-search{display:none;}
 th.th-sort::after{content:'';}}
"""

_JS_HELPERS = r"""
var REG={};
function fmtINR(n){n=Math.round(Number(n)||0);var neg=n<0;n=Math.abs(n);
 var s=String(n);var last3=s.length>3?s.slice(-3):s;
 var rest=s.length>3?s.slice(0,-3):'';
 if(rest){rest=rest.replace(/\B(?=(\d{2})+(?!\d))/g,',');}
 var out=rest?rest+','+last3:last3;return '₹'+(neg?'-':'')+out;}
function abbr(n){n=Number(n)||0;var a=Math.abs(n);
 if(a>=1e7)return '₹'+(n/1e7).toFixed(2)+'Cr';
 if(a>=1e5)return '₹'+(n/1e5).toFixed(1)+'L';
 return fmtINR(n);}
var PALETTE=__PALETTE__;
function col(i){return PALETTE[i%PALETTE.length];}
Chart.defaults.font.family="'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
Chart.defaults.color="#475569";
Chart.defaults.plugins.legend.labels.usePointStyle=true;
Chart.defaults.plugins.legend.labels.boxWidth=8;
// The VALUE lives on the axis opposite the category (indexAxis) axis:
// a horizontal bar (indexAxis='y') carries its value on parsed.x — reading
// parsed.y there returned the category INDEX (0,1,2…), the "₹0 / ₹1" bug.
function valueOf(c){var t=c.chart.config.type;
 if(t==='doughnut'||t==='pie')return c.parsed;
 var ax=(c.chart.options.indexAxis==='y')?'x':'y';
 return (c.parsed&&c.parsed[ax]!==undefined&&c.parsed[ax]!==null)
   ?c.parsed[ax]:c.parsed;}
function tipLabel(c){var l=c.dataset.label||'';var raw=valueOf(c);
 if(c.dataset.unit==='count')return (l?l+': ':'')+raw;
 return (l?l+': ':'')+fmtINR(raw);}
function axisOpts(unit,horizontal,stacked){
 var valTick=(unit==='count')?{precision:0}:{callback:function(v){return abbr(v);}};
 var valAxis={beginAtZero:true,stacked:stacked,ticks:valTick,
   grid:{color:'#EEF2F7'}};
 var catAxis={stacked:stacked,grid:{display:false}};
 return horizontal?{x:valAxis,y:catAxis}:{x:catAxis,y:valAxis};}
// Remember a chart's ORIGINAL data so the Sort / Top-N controls can
// re-derive the view without recomputing anything server-side.
function reg(id,type,labels,datasets,bg,chart){
 REG[id]={type:type,labels:labels.slice(),
  data:datasets.map(function(d){return d.data.slice();}),bg:bg,chart:chart};}
function groupedBar(id,labels,datasets,unit,horizontal,stacked){
 var el=document.getElementById(id);if(!el)return;
 var single=datasets.length===1;
 var bg=datasets.map(function(d,i){
   return single?labels.map(function(_,j){return col(j);}):col(i);});
 datasets.forEach(function(d,i){d.unit=unit;d.backgroundColor=bg[i];
   d.borderRadius=4;d.maxBarThickness=46;});
 var ch=new Chart(el,{type:'bar',
  data:{labels:labels.slice(),datasets:datasets},
  options:{indexAxis:horizontal?'y':'x',responsive:true,
   maintainAspectRatio:false,
   plugins:{legend:{display:!single,position:'top'},
     tooltip:{callbacks:{label:tipLabel}}},
   scales:axisOpts(unit,horizontal,stacked)}});
 reg(id,'bar',labels,datasets,bg,ch);}
function donut(id,labels,values){var el=document.getElementById(id);if(!el)return;
 var bg=labels.map(function(_,i){return col(i);});
 var ds=[{data:values.slice(),backgroundColor:bg,borderColor:'#fff',
   borderWidth:2}];
 var ch=new Chart(el,{type:'doughnut',data:{labels:labels.slice(),datasets:ds},
  options:{responsive:true,maintainAspectRatio:false,cutout:'58%',
   plugins:{legend:{position:'right'},tooltip:{callbacks:{label:function(c){
     var t=c.dataset.data.reduce(function(a,b){return a+(Number(b)||0);},0);
     var p=t?(c.parsed/t*100).toFixed(1):0;
     return c.label+': '+fmtINR(c.parsed)+' ('+p+'%)';}}}}}});
 reg(id,'doughnut',labels,ds,[bg],ch);}
function lineChart(id,labels,datasets,unit){var el=document.getElementById(id);
 if(!el)return;
 datasets.forEach(function(d,i){d.unit=unit;d.borderColor=col(i);
   d.backgroundColor=col(i);d.tension=.3;d.borderWidth=2;
   d.pointRadius=3;d.fill=false;});
 new Chart(el,{type:'line',data:{labels:labels,datasets:datasets},
  options:{responsive:true,maintainAspectRatio:false,
   plugins:{legend:{position:'top'},tooltip:{callbacks:{label:tipLabel}}},
   scales:axisOpts(unit,false,false)}});}
function sortOrder(o,mode){
 var idx=o.labels.map(function(_,i){return i;});
 var v=function(i){return Math.abs(Number(o.data[0][i])||0);};
 if(mode==='valDesc')idx.sort(function(a,b){return v(b)-v(a);});
 else if(mode==='valAsc')idx.sort(function(a,b){return v(a)-v(b);});
 else if(mode==='nameAsc')idx.sort(function(a,b){
   return String(o.labels[a]).localeCompare(String(o.labels[b]));});
 else if(mode==='nameDesc')idx.sort(function(a,b){
   return String(o.labels[b]).localeCompare(String(o.labels[a]));});
 return idx;}
function applyControls(id){var o=REG[id];if(!o)return;
 var ss=document.querySelector("select[data-ctrl='sort'][data-target='"+id+"']");
 var ts=document.querySelector("select[data-ctrl='top'][data-target='"+id+"']");
 var mode=ss?ss.value:'default';var top=ts?ts.value:'all';
 var order=sortOrder(o,mode);
 if(top!=='all')order=order.slice(0,parseInt(top,10));
 var ch=o.chart;
 ch.data.labels=order.map(function(i){return o.labels[i];});
 ch.data.datasets.forEach(function(ds,di){
   ds.data=order.map(function(i){return o.data[di][i];});
   if(Array.isArray(o.bg[di]))
     ds.backgroundColor=order.map(function(i){return o.bg[di][i];});});
 ch.update();}
"""

_JS_TABLES = r"""
// Numeric value parsed from a formatted cell ("₹-9,77,331" -> -977331,
// "63.7%" -> 63.7, "—"/"" -> null so blanks sort to the end).
function numVal(t){t=String(t).replace(/[₹,%\s]/g,'');
 if(t===''||t==='—'||t==='-')return null;
 var n=parseFloat(t);return isNaN(n)?null:n;}
function sortTable(tid,col){var table=document.getElementById(tid);
 if(!table||!table.tHead)return;
 var th=table.tHead.rows[0].cells[col];
 var asc=th.getAttribute('data-asc')!=='1';
 Array.prototype.forEach.call(table.tHead.rows[0].cells,function(c){
   c.removeAttribute('data-asc');c.classList.remove('sorted-asc','sorted-desc');});
 th.setAttribute('data-asc',asc?'1':'0');
 th.classList.add(asc?'sorted-asc':'sorted-desc');
 var numeric=th.classList.contains('num');
 var tb=table.tBodies[0];
 var rows=Array.prototype.slice.call(tb.querySelectorAll('tr:not(.total)'));
 var total=tb.querySelector('tr.total');
 rows.sort(function(a,b){
   var x=a.cells[col].textContent.trim(),y=b.cells[col].textContent.trim(),r;
   if(numeric){var nx=numVal(x),ny=numVal(y);
     if(nx===null&&ny===null)r=0;else if(nx===null)r=1;
     else if(ny===null)r=-1;else r=nx-ny;}
   else r=x.localeCompare(y);
   return asc?r:-r;});
 rows.forEach(function(r){tb.appendChild(r);});
 if(total)tb.appendChild(total);}
function filterTable(input){
 var table=document.getElementById(input.getAttribute('data-target'));
 if(!table)return;var q=input.value.trim().toLowerCase();
 Array.prototype.forEach.call(table.tBodies[0].querySelectorAll('tr:not(.total)'),
   function(r){r.style.display=(!q||r.textContent.toLowerCase().indexOf(q)>=0)
     ?'':'none';});}
function setupTables(){
 Array.prototype.forEach.call(document.querySelectorAll('table.sortable'),
  function(table){var tid=table.id;if(!table.tHead)return;
   Array.prototype.forEach.call(table.tHead.rows[0].cells,function(th,i){
     th.classList.add('th-sort');th.title='Click to sort';
     th.addEventListener('click',function(){sortTable(tid,i);});});});}
"""


def generate_dashboard(data: MISData, path: str | Path,
                       compare: MISData | None = None) -> Path:
    """Write the interactive HTML dashboard for *data* to *path*."""
    global _table_seq
    _table_seq = 0
    lbl = report._labels()
    ch = _Charts()

    # KPIs.
    rev, cost, profit = data.total_revenue, data.total_cost, data.total_profit
    target = sum(c.target for c in data.cost_centres)
    variance = rev - target

    def _delta(cur, prev):
        if compare is None or not prev:
            return ""
        d = cur - prev
        arrow = "▲" if d >= 0 else "▼"
        return f"{arrow} {_money(abs(d))} vs comparison"

    kpis = "".join([
        _kpi_card("Total Revenue", _money(rev), "#2F7DF6",
                  _delta(rev, compare.total_revenue if compare else 0)),
        _kpi_card("Total Cost", _money(cost), "#DC2626",
                  _delta(cost, compare.total_cost if compare else 0)),
        _kpi_card("Net Profit", _money(profit), "#16A34A",
                  _delta(profit, compare.total_profit if compare else 0)),
        _kpi_card("Net Margin", _pct(profit, rev), "#7C3AED"),
        _kpi_card("Total Target", _money(target), "#0891B2"),
        _kpi_card("Variance vs Target", _money(variance),
                  "#16A34A" if variance >= 0 else "#DC2626",
                  "Revenue − Target"),
    ])

    sections = [
        _cost_centre_section(data, ch),
        _budget_section(data, lbl, ch),
        _entity_section(data, ch),
        _service_section(data, ch),
        _partner_manager_section(data, ch),
        _client_section(data, lbl, ch),
        _provision_section(data, lbl, ch),
        _employee_section(data, ch),
        _client_register_section(data, ch),
    ]
    sections = [s for s in sections if s]

    nav_items = [("ccpl", "Cost Centre P&L"), ("budget", "Budget"),
                 ("entity", "Entity"), ("service", "Service"),
                 ("pm", "Partner–Manager"), ("clients", "Clients"),
                 ("provisions", "Provisions"), ("employees", "Employees"),
                 ("clientreg", "Client Register")]
    present = {s.split("id='", 1)[1].split("'", 1)[0] for s in sections}
    nav = "".join(f"<a href='#{a}'>{_esc(t)}</a>"
                  for a, t in nav_items if a in present)

    periods = ", ".join(report._month_short(p) for p in data.options.periods) \
        or "—"
    cmp_txt = (" · vs " + ", ".join(report._month_short(p)
                                    for p in compare.options.periods)
               if compare else "")
    warn = ""
    if data.warnings:
        items = "".join(f"<div>• {_esc(w)}</div>" for w in data.warnings)
        warn = f"<div class='warn'><b>Notes</b>{items}</div>"

    gen_on = _dt.date.today().strftime("%d %b %Y")
    helpers = (_JS_HELPERS.replace("__PALETTE__", json.dumps(_PALETTE))
               + _JS_TABLES)

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(config.ORG_NAME)} — MIS Dashboard</title>
<style>{_CSS}</style>{_chartjs_tag()}</head><body>
<header class="top">
  <h1>{_esc(config.ORG_NAME)}</h1>
  <div class="sub">Management Information System — Interactive Dashboard</div>
  <div class="meta">Reporting period(s): <b>{_esc(periods)}</b>{_esc(cmp_txt)}
   &nbsp;·&nbsp; Generated on <b>{gen_on}</b>
   &nbsp;·&nbsp; Reimbursements: <b>{'Included' if data.options.include_reimbursement else 'Excluded'}</b></div>
</header>
<nav>{nav}<button class="print" onclick="window.print()">⎙ Print / PDF</button></nav>
<main>
  {warn}
  <div class="kpis">{kpis}</div>
  {''.join(sections)}
</main>
<footer>Figures tie to the generated Excel MIS (same computed dataset).
 Generated by {_esc(config.APP_SHORT)}.</footer>
<script>{helpers}</script>
<script>
setupTables();
try{{
{ch.script()}
}}catch(e){{console.error(e);
 document.querySelectorAll('.chart-box').forEach(function(b){{
   b.innerHTML='<div style="color:#94A3B8;font-size:13px;padding:20px">'+
   'Chart unavailable — see the table.</div>';}});}}
</script>
</body></html>"""

    path = Path(path)
    path.write_text(doc, encoding="utf-8")
    return path
