"""Calculation engine — the analytical core of the MIS.

For a selected set of calendar-month periods it produces:

* **Fact rows** — flat revenue / expense / labour lines, each tagged with every
  dimension (period, entity, cost centre, manager, service, client/employee).
  Phase 6 writes these into the workbook's data sheets so the summary sheets
  can aggregate them with live Excel formulas.
* **Summaries** — cost-centre, Partner–Manager, entity and service roll-ups,
  used by the Dashboard and as a cross-check on the workbook.

Labour costing
--------------
An employee's monthly pay (salary, plus reimbursements when that toggle is on)
is the *amount*; the timesheet decides the *allocation*. Pay is spread across
the clients the employee logged hours against, at an hourly rate of
``pay ÷ total hours``. Each client carries a cost centre, so cross-client work
naturally lands on the right cost centre. Hours on non-billable / unmapped
clients fall to the Office (overhead) cost centre. If an employee has pay but
no timesheet hours, the whole amount falls back to the cost centre named on the
salary sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..database import transaction
from .resolution import norm

OVERHEAD_SEPARATE = "separate"
OVERHEAD_REVENUE = "revenue"
OVERHEAD_EQUAL = "equal"


@dataclass
class MISOptions:
    """Operator-chosen toggles for one MIS run."""
    periods: list[str]
    include_reimbursement: bool = True
    overhead_mode: str = OVERHEAD_SEPARATE      # separate | revenue | equal


@dataclass
class CostCentreLine:
    cost_centre_id: int | None
    code: str
    name: str
    is_office: bool = False
    revenue: float = 0.0
    direct_expense: float = 0.0
    labour: float = 0.0
    allocated_overhead: float = 0.0
    target: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.direct_expense + self.labour + self.allocated_overhead

    @property
    def profit(self) -> float:
        return self.revenue - self.total_cost

    @property
    def variance(self) -> float:
        return self.profit - self.target


@dataclass
class MISData:
    """Everything one MIS run needs."""
    options: MISOptions
    revenue_facts: list[dict] = field(default_factory=list)
    expense_facts: list[dict] = field(default_factory=list)
    labour_facts: list[dict] = field(default_factory=list)
    cost_centres: list[CostCentreLine] = field(default_factory=list)
    partner_manager: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_revenue(self) -> float:
        return sum(c.revenue for c in self.cost_centres)

    @property
    def total_cost(self) -> float:
        return sum(c.total_cost for c in self.cost_centres)

    @property
    def total_profit(self) -> float:
        return self.total_revenue - self.total_cost


# --- financial year ----------------------------------------------------------

def financial_year(period: str) -> str:
    """'2026-01' -> '2025-26' (Indian Apr–Mar financial year)."""
    year, month = int(period[:4]), int(period[5:7])
    start = year if month >= 4 else year - 1
    return f"{start}-{str(start + 1)[-2:]}"


# --- main entry point --------------------------------------------------------

def compute(options: MISOptions) -> MISData:
    """Run the full calculation for the selected periods.

    Re-runs name resolution before reading masters so any client /
    employee master rows the operator added since the last import get
    picked up. Otherwise timesheet ``client_raw`` rows imported before
    a client was added stay forever unresolved — exactly the symptom
    behind the "Salary sheet only shows unallocated time" report.
    """
    data = MISData(options=options)
    if not options.periods:
        data.warnings.append("No period selected.")
        return data

    # Cheap idempotent sweep — picks up any new master rows the
    # operator added since the last import so unresolved timesheet /
    # voucher rows finally get their client_id. We deliberately
    # skip the fuzzy pass here: it's risky to introduce new fuzzy
    # auto-links at report-generation time (operator can't see what
    # happened), and the v0.3.50 fuzzy logic already runs as part of
    # imports + Master Data add/edit. Only the safe exact / alias
    # matches fire at build time.
    from .resolution import apply_known_client_aliases
    apply_known_client_aliases(skip_fuzzy=True)

    masters = _load_masters()
    _build_voucher_facts(data, options, masters)
    _build_labour_facts(data, options, masters)
    _roll_up(data, masters)
    return data


# --- master lookups ----------------------------------------------------------

def _load_masters() -> dict:
    with transaction() as conn:
        cost_centres = {r["id"]: dict(r)
                        for r in conn.execute("SELECT * FROM cost_centres")}
        managers = {r["id"]: dict(r)
                    for r in conn.execute("SELECT * FROM managers")}
        entities = {r["id"]: dict(r)
                    for r in conn.execute("SELECT * FROM entities")}
        services = {r["id"]: dict(r)
                    for r in conn.execute("SELECT * FROM services")}
        clients = {r["id"]: dict(r)
                   for r in conn.execute("SELECT * FROM clients")}
        # name -> employee id (master names + aliases). Insert aliases
        # FIRST so canonical names overwrite them on key collision —
        # the same correctness fix applied to clients in v0.3.58.
        # Otherwise a stale fuzzy alias silently outranks the operator's
        # authoritative master row.
        emp_index: dict[str, int] = {}
        for r in conn.execute("SELECT employee_id, alias_text FROM employee_aliases"):
            emp_index[norm(r["alias_text"])] = r["employee_id"]
        for r in conn.execute("SELECT id, name FROM employees"):
            emp_index[norm(r["name"])] = r["id"]
        employees = {r["id"]: dict(r)
                     for r in conn.execute("SELECT * FROM employees")}
    office_id = next((cid for cid, c in cost_centres.items()
                      if c["cc_type"] == "office"), None)
    return {
        "cost_centres": cost_centres, "managers": managers,
        "entities": entities, "services": services, "clients": clients,
        "emp_index": emp_index, "employees": employees, "office_id": office_id,
    }


def _placeholders(items: list) -> str:
    return ",".join("?" * len(items))


# --- revenue & expense facts -------------------------------------------------

def _build_voucher_facts(data: MISData, options: MISOptions, masters: dict) -> None:
    ph = _placeholders(options.periods)
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT v.period, v.txn_date, v.vch_no, v.entity_id, v.client_id, "
            f"  v.kind, v.description, "
            f"  s.amount, s.cost_centre_id, s.manager_id, s.service_id "
            f"FROM voucher_splits s JOIN vouchers v ON v.id = s.voucher_id "
            f"WHERE v.period IN ({ph})", options.periods).fetchall()
    for r in rows:
        fact = {
            "period": r["period"],
            "txn_date": r["txn_date"], "vch_no": r["vch_no"],
            "entity_id": r["entity_id"],
            "cost_centre_id": r["cost_centre_id"], "manager_id": r["manager_id"],
            "service_id": r["service_id"], "client_id": r["client_id"],
            "amount": float(r["amount"] or 0.0),
        }
        if r["kind"] == "sales":
            data.revenue_facts.append(fact)
        else:
            # Unassigned expense cost centre -> Office overhead.
            if fact["cost_centre_id"] is None:
                fact["cost_centre_id"] = masters["office_id"]
            fact["description"] = r["description"]
            data.expense_facts.append(fact)


# --- labour facts ------------------------------------------------------------

def _build_labour_facts(data: MISData, options: MISOptions, masters: dict) -> None:
    """Build per-(employee, client/CC) salary-cost facts for the period.

    Each employee's monthly cost = ``salary_paid`` (+ optional
    ``reimbursement``) + ``fixed_office_overhead.amount_per_employee``
    for that period. That total is divided by ``days_in_month * 8`` to
    get an hourly rate (the firm's standard month-hours, not actual
    timesheet hours — so an under-filled timesheet doesn't inflate the
    rate). Each timesheet line then books ``hours × rate`` against the
    client's cost centre.

    Any residual hours (``standard_month_hours - sum(timesheet_hours)``,
    if positive) are booked to the employee's home cost centre
    (``employees.default_cost_centre_id``, fallback to the salary
    sheet's CC, fallback to Office) so the FULL monthly cost lands
    somewhere — no labour cost silently vanishes.
    """
    import calendar
    office_id = masters["office_id"]
    clients = masters["clients"]
    emp_index = masters["emp_index"]
    employees = masters["employees"]
    ph = _placeholders(options.periods)

    with transaction() as conn:
        salary_rows = conn.execute(
            f"SELECT period, employee_name, cost_centre_id, salary_paid, "
            f"reimbursement FROM salary_entries WHERE period IN ({ph})",
            options.periods).fetchall()
        ts_rows = conn.execute(
            f"SELECT period, txn_date, emp_name, client_raw, client_id, "
            f"       hours, is_billable "
            f"FROM timesheet_entries WHERE period IN ({ph})",
            options.periods).fetchall()
        overhead_rows = conn.execute(
            f"SELECT period, amount_per_employee FROM fixed_office_overhead "
            f"WHERE period IN ({ph}) AND active = 1",
            options.periods).fetchall()
    overhead_by_period = {r["period"]: float(r["amount_per_employee"] or 0.0)
                           for r in overhead_rows}

    def emp_key(name: str):
        return emp_index.get(norm(name), f"raw:{norm(name)}")

    def standard_hours(period: str) -> float:
        try:
            y, m = int(period[:4]), int(period[5:7])
            return calendar.monthrange(y, m)[1] * 8.0
        except (ValueError, IndexError):
            return 30 * 8.0

    # Pay pool per (period, employee).
    pay: dict[tuple, dict] = {}
    for r in salary_rows:
        key = (r["period"], emp_key(r["employee_name"]))
        amt = float(r["salary_paid"] or 0.0)
        if options.include_reimbursement:
            amt += float(r["reimbursement"] or 0.0)
        rec = pay.setdefault(key, {"amount": 0.0, "fallback_cc": None,
                                   "name": r["employee_name"]})
        rec["amount"] += amt
        if r["cost_centre_id"] is not None:
            rec["fallback_cc"] = r["cost_centre_id"]

    # Timesheet hours per (period, employee).
    hours: dict[tuple, list] = {}
    for r in ts_rows:
        key = (r["period"], emp_key(r["emp_name"]))
        hours.setdefault(key, []).append(r)

    for key, rec in pay.items():
        period, emp_lookup_key = key
        rows = hours.get(key, [])
        total_logged = sum(float(t["hours"] or 0.0) for t in rows)
        overhead = overhead_by_period.get(period, 0.0)
        total_cost = rec["amount"] + overhead
        std_hours = standard_hours(period)
        rate = total_cost / std_hours if std_hours else 0.0

        # Home CC: master record → fallback to salary's CC → Office.
        home_cc = rec["fallback_cc"]
        if isinstance(emp_lookup_key, int):
            home_cc = (employees.get(emp_lookup_key) or {}).get(
                "default_cost_centre_id") or home_cc
        home_cc = home_cc or office_id

        if total_logged > 0:
            for t in rows:
                h = float(t["hours"] or 0.0)
                if not h:
                    continue
                cc = _client_cost_centre(t, clients, office_id)
                data.labour_facts.append({
                    "period": period,
                    "txn_date": t["txn_date"],
                    "cost_centre_id": cc,
                    "employee_name": rec["name"],
                    "client_id": t["client_id"],
                    # Preserve the raw text from the timesheet so the
                    # Salary sheet can show it when the client_id link
                    # hasn't been resolved yet (much more useful than
                    # printing "(unmapped)" with no further info).
                    "client_raw": t["client_raw"],
                    "is_residual": False,
                    "hours": h, "amount": h * rate,
                })
            # Residual hours go to the employee's home CC so the FULL
            # monthly cost (salary + overhead) gets allocated.
            residual = std_hours - total_logged
            if residual > 0.01 and rate > 0:
                data.labour_facts.append({
                    "period": period,
                    "txn_date": None,
                    "cost_centre_id": home_cc,
                    "employee_name": rec["name"],
                    "client_id": None,
                    "client_raw": None,
                    "is_residual": True,
                    "hours": residual, "amount": residual * rate,
                })
        elif total_cost:
            # No hours logged — entire monthly cost to the home CC.
            data.labour_facts.append({
                "period": period,
                "txn_date": None,
                "cost_centre_id": home_cc,
                "employee_name": rec["name"],
                "client_id": None,
                "client_raw": None,
                "is_residual": True,
                "hours": std_hours, "amount": total_cost,
            })

    # Even employees with no salary entry can have a per-period overhead
    # — but without salary data we can't know they exist. The overhead
    # is therefore only applied alongside an existing salary row. This
    # matches the operator's workflow: salary upload is monthly; the
    # overhead figure rides on top of whoever appears on that month's
    # salary sheet.


def _client_cost_centre(ts_row, clients: dict, office_id: int | None):
    """Cost centre a timesheet line's labour belongs to."""
    if not ts_row["is_billable"]:
        return office_id
    client = clients.get(ts_row["client_id"])
    if client and client["cost_centre_id"] is not None:
        return client["cost_centre_id"]
    return office_id


# --- roll-ups ----------------------------------------------------------------

def _roll_up(data: MISData, masters: dict) -> None:
    cost_centres = masters["cost_centres"]
    office_id = masters["office_id"]
    options = data.options

    lines: dict[int | None, CostCentreLine] = {}

    def line_for(cc_id):
        if cc_id not in lines:
            cc = cost_centres.get(cc_id)
            if cc:
                lines[cc_id] = CostCentreLine(
                    cc_id, cc["code"], cc["name"],
                    is_office=(cc["cc_type"] == "office"))
            else:
                lines[cc_id] = CostCentreLine(cc_id, "—", "Unassigned")
        return lines[cc_id]

    for f in data.revenue_facts:
        line_for(f["cost_centre_id"]).revenue += f["amount"]
    for f in data.expense_facts:
        line_for(f["cost_centre_id"]).direct_expense += f["amount"]
    for f in data.labour_facts:
        line_for(f["cost_centre_id"]).labour += f["amount"]

    # Targets (annual, pro-rated to the number of months selected).
    fys = {financial_year(p) for p in options.periods}
    months = len(options.periods)
    with transaction() as conn:
        for cc_id, line in lines.items():
            if cc_id is None:
                continue
            total = 0.0
            for fy in fys:
                row = conn.execute(
                    "SELECT target_amount FROM targets "
                    "WHERE financial_year = ? AND cost_centre_id = ?",
                    (fy, cc_id)).fetchone()
                if row:
                    total += float(row["target_amount"]) / 12.0 * months
            line.target = total

    # Overhead allocation.
    _allocate_overhead(lines, office_id, options.overhead_mode)

    data.cost_centres = sorted(
        lines.values(),
        key=lambda l: (l.is_office, l.cost_centre_id is not None and 0 or 1,
                       -l.revenue))
    _roll_up_dimensions(data, masters)


def _allocate_overhead(lines: dict, office_id, mode: str) -> None:
    office = lines.get(office_id)
    if office is None or mode == OVERHEAD_SEPARATE:
        return
    pool = office.total_cost - office.revenue
    if pool <= 0:
        return
    partners = [l for cid, l in lines.items()
                if cid is not None and not l.is_office]
    if not partners:
        return
    if mode == OVERHEAD_EQUAL:
        share = pool / len(partners)
        for l in partners:
            l.allocated_overhead += share
    else:  # by revenue
        total_rev = sum(l.revenue for l in partners)
        if total_rev <= 0:
            share = pool / len(partners)
            for l in partners:
                l.allocated_overhead += share
        else:
            for l in partners:
                l.allocated_overhead += pool * l.revenue / total_rev
    # Office's own cost is now carried by the partners.
    office.direct_expense = 0.0
    office.labour = 0.0


def _roll_up_dimensions(data: MISData, masters: dict) -> None:
    """Partner-Manager, entity and service summaries."""
    cc = masters["cost_centres"]
    mgr = masters["managers"]
    ent = masters["entities"]
    svc = masters["services"]

    # Partner – Manager (revenue and direct expense).
    pm: dict[tuple, dict] = {}

    def pm_line(cc_id, mgr_id):
        key = (cc_id, mgr_id)
        if key not in pm:
            cc_code = cc.get(cc_id, {}).get("code", "—")
            mgr_code = mgr.get(mgr_id, {}).get("code", "(unassigned)")
            pm[key] = {"label": f"{cc_code} – {mgr_code}",
                       "cost_centre_id": cc_id, "manager_id": mgr_id,
                       "revenue": 0.0, "direct_expense": 0.0}
        return pm[key]

    for f in data.revenue_facts:
        pm_line(f["cost_centre_id"], f["manager_id"])["revenue"] += f["amount"]
    for f in data.expense_facts:
        pm_line(f["cost_centre_id"], f["manager_id"])["direct_expense"] += f["amount"]
    data.partner_manager = sorted(pm.values(), key=lambda d: -d["revenue"])

    # Entity.
    ent_agg: dict = {}
    for f in data.revenue_facts:
        e = ent_agg.setdefault(f["entity_id"], {"revenue": 0.0, "direct_expense": 0.0})
        e["revenue"] += f["amount"]
    for f in data.expense_facts:
        e = ent_agg.setdefault(f["entity_id"], {"revenue": 0.0, "direct_expense": 0.0})
        e["direct_expense"] += f["amount"]
    data.entities = [
        {"name": ent.get(eid, {}).get("name", "(unspecified)"),
         "entity_id": eid, **vals}
        for eid, vals in sorted(ent_agg.items(),
                                key=lambda kv: -kv[1]["revenue"])]

    # Service.
    svc_agg: dict = {}
    for f in data.revenue_facts:
        s = svc_agg.setdefault(f["service_id"], {"revenue": 0.0, "direct_expense": 0.0})
        s["revenue"] += f["amount"]
    for f in data.expense_facts:
        s = svc_agg.setdefault(f["service_id"], {"revenue": 0.0, "direct_expense": 0.0})
        s["direct_expense"] += f["amount"]
    data.services = [
        {"name": svc.get(sid, {}).get("name", "(unspecified)"),
         "service_id": sid, **vals}
        for sid, vals in sorted(svc_agg.items(),
                                key=lambda kv: -kv[1]["revenue"])]
