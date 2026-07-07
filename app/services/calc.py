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

Office overhead (v0.3.69)
-------------------------
Office overhead is no longer a management-entered master figure. It is
computed from the books: the period's **indirect expenses booked to the
Office cost centre** (rent, staff welfare, electricity, …) divided by the
number of **active employees** (distinct employees who filed timesheet
hours that period). Each active employee carries one per-head share to
their home cost centre; a single negative offset row on Office keeps the
pool from double-counting (it already sits in Office's direct expenses).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..database import transaction
from ..util import month_label
from .resolution import norm

OVERHEAD_SEPARATE = "separate"
OVERHEAD_REVENUE = "revenue"
OVERHEAD_EQUAL = "equal"

# --- expense classification --------------------------------------------------

EXPENSE_TYPE_PROFESSIONAL = "Professional Fees"
EXPENSE_TYPE_INDIRECT = "Indirect Expense"

_PROFESSIONAL_RE = re.compile(r"professional", re.IGNORECASE)
_PROF_TAX_RE = re.compile(r"professional\s+tax", re.IGNORECASE)


def expense_type(service_name: str | None) -> str:
    """Bifurcate an expense ledger head into the firm's two buckets.

    * ``Professional Fees`` — sub-contracted professional work, a DIRECT
      cost of the partner ("Professional Fees", "Legal & Professional
      Fees", "Professional Charges", …).
    * ``Indirect Expense`` — everything else (rent, staff welfare,
      electricity, courier, …). "Professional Tax" is a statutory levy,
      not bought-in work, so it stays indirect.
    """
    s = service_name or ""
    if _PROFESSIONAL_RE.search(s) and not _PROF_TAX_RE.search(s):
        return EXPENSE_TYPE_PROFESSIONAL
    return EXPENSE_TYPE_INDIRECT


# --- revenue classification --------------------------------------------------

_REIMB_KEYWORDS = ("reimbur",)
_OPE_KEYWORDS = ("out of pocket", "out-of-pocket", " ope", "oop")
_OTHER_KEYWORDS = ("round off", "roundoff", "round-off")


def revenue_category(service_name: str | None) -> str:
    """Bucket a revenue ledger head: ``Income`` (normal sales) /
    ``Reimbursement`` / ``OPE`` (out-of-pocket recoveries) / ``Other``
    (round-off). The canonical classifier used by both the Revenue data
    sheet's Category column and the Cost Centre P&L revenue split, so the
    Excel formulas and the calc roll-ups always agree."""
    if not service_name:
        return "Income"
    s = service_name.lower()
    if any(k in s for k in _REIMB_KEYWORDS):
        return "Reimbursement"
    if any(k in s for k in _OPE_KEYWORDS) or s.strip() == "ope":
        return "OPE"
    if any(k in s for k in _OTHER_KEYWORDS):
        return "Other"
    return "Income"


@dataclass
class MISOptions:
    """Operator-chosen toggles for one MIS run."""
    periods: list[str]
    include_reimbursement: bool = True
    overhead_mode: str = OVERHEAD_SEPARATE      # retained for compatibility
    # Locations to consider for the Employee Register / office-overhead
    # computation (v0.3.98). ``None`` = no filter (all locations). When a
    # list is given, only employees whose master location is in it (plus
    # employees with NO location assigned) enter the register and the
    # overhead pool/spread. Voucher/salary FIGURES are never filtered —
    # only the register and the overhead allocation.
    location_ids: list[int] | None = None


@dataclass
class CostCentreLine:
    cost_centre_id: int | None
    code: str
    name: str
    is_office: bool = False
    # Income side (v0.3.89 split): sales income vs reimbursement/OPE recovery.
    revenue: float = 0.0                 # Income + Other (sales)
    reimbursement_income: float = 0.0    # Reimbursement + OPE recoveries
    # Cost side: voucher expenses (+ provisions) vs reimbursement outlays.
    direct_expense: float = 0.0          # voucher expenses + provisions
    reimbursement_expense: float = 0.0   # reimbursement-sheet outlays
    labour: float = 0.0
    allocated_overhead: float = 0.0
    target: float = 0.0

    @property
    def total_income(self) -> float:
        return self.revenue + self.reimbursement_income

    @property
    def total_cost(self) -> float:
        return (self.direct_expense + self.reimbursement_expense
                + self.labour + self.allocated_overhead)

    @property
    def profit(self) -> float:
        return self.total_income - self.total_cost

    @property
    def variance(self) -> float:
        return self.revenue - self.target


@dataclass
class MISData:
    """Everything one MIS run needs."""
    options: MISOptions
    revenue_facts: list[dict] = field(default_factory=list)
    expense_facts: list[dict] = field(default_factory=list)
    labour_facts: list[dict] = field(default_factory=list)
    reimbursement_facts: list[dict] = field(default_factory=list)
    # Remaining (unadjusted) provision costs, carried forward to the
    # reporting month — direct costs the cost centre expects but hasn't
    # yet incurred. See :func:`_build_provision_facts`.
    provision_facts: list[dict] = field(default_factory=list)
    # One entry per selected period: clients billed that period, with new
    # (first-billed) and lost (billed last month, not this) clients, by
    # cost centre. The client analogue of the employee register. See
    # :func:`_build_client_register`.
    client_register: list[dict] = field(default_factory=list)
    # One entry per selected period: active-employee roster (from the
    # timesheet), joiners/exits vs the previous month, and the office
    # overhead computation (indirect pool ÷ active headcount). Feeds the
    # Employee Register sheet AND the per-employee overhead labour facts.
    employee_register: list[dict] = field(default_factory=list)
    cost_centres: list[CostCentreLine] = field(default_factory=list)
    partner_manager: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Human-readable label of the location selection ("All locations" or
    # "Mumbai, Bangalore") — shown on the workbook Cover.
    location_label: str = "All locations"

    @property
    def total_revenue(self) -> float:
        # Total billed = sales income + reimbursement/OPE recoveries.
        return sum(c.total_income for c in self.cost_centres)

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


def normalize_fy(value) -> str:
    """Canonicalise an operator-typed financial year to ``YYYY-YY``.

    Operators type these loosely in the Targets master — ``2026 - 27``,
    ``2026-2027``, ``2026/27`` — but :func:`financial_year` produces the
    tight ``YYYY-YY`` form, and target lookups did an exact string match.
    A stray space therefore made the MIS Target column (and the
    Budget-vs-Sales sheet) silently read 0. Normalising both sides before
    comparing fixes that. Returns the whitespace-stripped input unchanged
    when it doesn't look like a financial year (so unexpected values still
    match themselves rather than collapsing together).
    """
    s = re.sub(r"\s+", "", str(value or ""))
    m = re.match(r"^(\d{4})[-/](\d{2,4})$", s)
    if not m:
        return s
    start, end = m.group(1), m.group(2)
    if len(end) == 4:           # '2026-2027' -> '2026-27'
        end = end[-2:]
    return f"{start}-{end}"


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
    if options.location_ids is not None:
        names = [masters["locations"].get(i, {}).get("name", f"#{i}")
                 for i in options.location_ids]
        data.location_label = ", ".join(sorted(names)) if names else "(none)"
        data.warnings.append(
            "Employee Register / office overhead consider ONLY employees "
            f"and partners of these locations: {data.location_label}. "
            "Employees and partners with no location assigned are left out "
            "(see the note below if any). Salary and voucher figures are "
            "not filtered.")
    _build_voucher_facts(data, options, masters)
    # Employee register BEFORE labour facts: the register's active-employee
    # roster + office-indirect pool drive the per-employee overhead facts.
    _build_employee_register(data, options, masters)
    _build_labour_facts(data, options, masters)
    _build_reimbursement_facts(data, options, masters)
    _build_provision_facts(data, options, masters)
    _build_client_register(data, options, masters)
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
        locations = {r["id"]: dict(r)
                     for r in conn.execute("SELECT * FROM locations")}
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
        "locations": locations,
        "emp_index": emp_index, "employees": employees, "office_id": office_id,
    }


def _location_filter(masters: dict, options: MISOptions):
    """Return a predicate: is this employee key considered in this run?

    ``options.location_ids`` = None → everyone (no filter). Otherwise
    STRICT (v0.3.101, operator ask): ONLY employees whose master location
    is in the selected set are considered — an employee with no location
    assigned, or an unresolved raw timesheet name (no master row at all),
    is left out of the register and the overhead computation. The
    exclusions are surfaced as a Cover warning so nothing drops silently.
    Applies only to the Employee Register and the office-overhead
    computation; salary/voucher figures are never location-filtered.
    """
    if options.location_ids is None:
        return lambda key: True
    allowed = set(options.location_ids)
    employees = masters["employees"]

    def included(key) -> bool:
        if not isinstance(key, int):
            return False        # unresolved raw name — has no location
        loc = (employees.get(key) or {}).get("location_id")
        return loc is not None and loc in allowed

    return included


def _placeholders(items: list) -> str:
    return ",".join("?" * len(items))


def _mgr_folder(masters: dict):
    """Return a function that folds a *deactivated* manager down to ``None``.

    Deactivating a manager in the master is the operator's way of saying
    "don't break the MIS down by this manager any more — just show the
    partner total". The captured data (voucher splits, employee→manager
    links) is left untouched, but at report-build time an inactive manager's
    id is treated as unassigned, so its figures fold into the partner's own
    column instead of getting a separate Partner-Manager column. Active
    managers (and ``None``) pass through unchanged. (v0.3.97)
    """
    managers = masters["managers"]

    def fold(mgr_id):
        if mgr_id is None:
            return None
        return mgr_id if (managers.get(mgr_id) or {}).get("active", 1) else None

    return fold


# --- revenue & expense facts -------------------------------------------------

def _build_voucher_facts(data: MISData, options: MISOptions, masters: dict) -> None:
    ph = _placeholders(options.periods)
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT v.period, v.txn_date, v.vch_no, v.invoice_no, "
            f"  v.entity_id, v.client_id, v.party_name, "
            f"  v.kind, v.description, "
            f"  s.amount, s.cost_centre_id, s.manager_id, s.service_id "
            f"FROM voucher_splits s JOIN vouchers v ON v.id = s.voucher_id "
            f"WHERE v.period IN ({ph})", options.periods).fetchall()
    services = masters["services"]
    fold_mgr = _mgr_folder(masters)
    for r in rows:
        fact = {
            "period": r["period"],
            "txn_date": r["txn_date"], "vch_no": r["vch_no"],
            "invoice_no": r["invoice_no"],
            "entity_id": r["entity_id"],
            "cost_centre_id": r["cost_centre_id"],
            "manager_id": fold_mgr(r["manager_id"]),
            "service_id": r["service_id"], "client_id": r["client_id"],
            # Raw party text — the Client column's fallback when the
            # party hasn't been linked to a client-master row (most
            # purchase-register vendors). The party IS the client/vendor
            # name as Tally knows it, so showing it beats "(unmapped)".
            "party_name": r["party_name"],
            "amount": float(r["amount"] or 0.0),
        }
        if r["kind"] == "sales":
            # Category drives the CC P&L revenue split (Income vs the
            # Reimbursement/OPE recovery) — same classifier the Revenue
            # sheet's Category column uses.
            svc_name = (services.get(r["service_id"]) or {}).get("name")
            fact["category"] = revenue_category(svc_name)
            data.revenue_facts.append(fact)
        else:
            # Unassigned expense cost centre -> Office overhead.
            if fact["cost_centre_id"] is None:
                fact["cost_centre_id"] = masters["office_id"]
            fact["description"] = r["description"]
            svc_name = (services.get(r["service_id"]) or {}).get("name")
            fact["expense_type"] = expense_type(svc_name)
            data.expense_facts.append(fact)


# --- employee register --------------------------------------------------------

def _prev_period(period: str) -> str:
    """'2026-04' -> '2026-03' (calendar-month arithmetic)."""
    y, m = int(period[:4]), int(period[5:7])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y:04d}-{m:02d}"


def _build_employee_register(data: MISData, options: MISOptions,
                              masters: dict) -> None:
    """Active-employee roster per period + the office-overhead computation.

    "Active" = the employee filed at least one timesheet row in the
    period (the timesheet is the operator's source of truth for who
    worked that month). Joiners/exits compare against the PREVIOUS
    calendar month's timesheet — read straight from the DB, so the
    previous month doesn't have to be part of the selected periods.

    Each period entry also carries the office-overhead computation
    that replaced the ``fixed_office_overhead`` master (v0.3.69):

        pool       = indirect expenses booked to the Office cost centre
        per_employee = pool ÷ active employee count

    The per-employee share is charged to each active employee's home
    cost centre by :func:`_build_labour_facts`.
    """
    emp_index = masters["emp_index"]
    employees = masters["employees"]
    office_id = masters["office_id"]
    cost_centres = masters["cost_centres"]

    periods = sorted(options.periods)
    prev_map = {p: _prev_period(p) for p in periods}
    all_periods = sorted(set(periods) | set(prev_map.values()))
    ph = _placeholders(all_periods)
    with transaction() as conn:
        ts_rows = conn.execute(
            f"SELECT DISTINCT period, emp_name FROM timesheet_entries "
            f"WHERE period IN ({ph}) AND emp_name <> ''",
            all_periods).fetchall()
        # Salary-sheet CC per (period, employee) — fallback for the home
        # cost centre when the employee master has no default CC. Same
        # chain _build_labour_facts uses.
        sal_rows = conn.execute(
            f"SELECT period, employee_name, cost_centre_id FROM salary_entries "
            f"WHERE period IN ({ph}) AND cost_centre_id IS NOT NULL",
            all_periods).fetchall()
        # Salary AMOUNTS for the selected periods — office-home employees'
        # pay joins the overhead pool (v0.3.82), so we need it here where
        # the pool is computed.
        sal_amt_rows = conn.execute(
            f"SELECT period, employee_name, salary_paid, reimbursement "
            f"FROM salary_entries WHERE period IN ({_placeholders(periods)})",
            periods).fetchall()

    def emp_key(name: str):
        return emp_index.get(norm(name), f"raw:{norm(name)}")

    # Location selection (v0.3.98; STRICT since v0.3.101): only employees
    # of the selected locations enter the register / overhead spread.
    # Untagged / unresolved names are excluded and reported via a warning.
    included = _location_filter(masters, options)
    filter_active = options.location_ids is not None
    excluded_untagged: set[str] = set()

    def _note_excluded(key, name: str) -> None:
        """Record an employee dropped ONLY because they carry no location
        (raw name, or master row with location NULL) — a tagging gap the
        operator should know about; a wrong-location exclusion is not
        noted (that's the filter working as intended)."""
        if not filter_active:
            return
        if not isinstance(key, int):
            excluded_untagged.add(name.strip() or "(unnamed)")
        elif (employees.get(key) or {}).get("location_id") is None:
            excluded_untagged.add(
                (employees.get(key) or {}).get("name") or name)

    sal_cc: dict[tuple, int] = {}
    for r in sal_rows:
        sal_cc[(r["period"], emp_key(r["employee_name"]))] = r["cost_centre_id"]

    # period -> {key: display name}. Master canonical name wins over the
    # raw timesheet spelling when the employee is resolved. Employees
    # outside the selected locations are left out entirely (so they are
    # neither Active nor Exits).
    roster: dict[str, dict] = {p: {} for p in all_periods}
    for r in ts_rows:
        key = emp_key(r["emp_name"])
        if not included(key):
            _note_excluded(key, r["emp_name"])
            continue
        name = r["emp_name"]
        if isinstance(key, int):
            name = (employees.get(key) or {}).get("name") or name
        roster.setdefault(r["period"], {})[key] = name

    # Partners are not in the employee master but ARE overhead recipients
    # (v0.3.98): every active partner cost centre counts as one head in
    # the overhead spread and carries a per-head share to its own CC.
    #
    # Partner location filter (v0.3.104): partners can now be tagged with a
    # location too. When the operator narrows the run to some locations, ONLY
    # partners of those locations count as recipient heads — mirroring the
    # STRICT employee filter (v0.3.101). An untagged partner (location NULL)
    # is dropped whenever a filter is active and named in a Cover warning;
    # a wrong-location partner is dropped silently (the filter doing its job).
    # With no filter (all locations) every active partner counts, as before.
    locations = masters["locations"]
    allowed_locs = set(options.location_ids) if filter_active else None
    excluded_partners_untagged: set[str] = set()
    partners = []
    for cc_id, cc in sorted(cost_centres.items(),
                            key=lambda kv: kv[1]["code"]):
        if cc["cc_type"] != "partner" or not cc.get("active", 1):
            continue
        loc_id = cc.get("location_id")
        if allowed_locs is not None:
            if loc_id is None:
                excluded_partners_untagged.add(cc["name"])
                continue
            if loc_id not in allowed_locs:
                continue
        partners.append({
            "key": f"partner:{cc['code']}",
            "name": cc["name"],
            "cost_centre_id": cc_id,
            "cc_code": cc["code"],
            "location": (locations.get(loc_id) or {}).get("name") or "—",
        })

    def home_cc(period: str, key) -> int | None:
        cc = None
        if isinstance(key, int):
            cc = (employees.get(key) or {}).get("default_cost_centre_id")
        return cc or sal_cc.get((period, key)) or office_id

    def cc_code(cc_id) -> str:
        return (cost_centres.get(cc_id) or {}).get("code") or "—"

    def loc_name(key) -> str:
        if not isinstance(key, int):
            return "—"
        loc_id = (employees.get(key) or {}).get("location_id")
        return (locations.get(loc_id) or {}).get("name") or "—"

    # Office indirect pool per period, from the already-built expense facts.
    pool_by_period: dict[str, float] = {p: 0.0 for p in periods}
    for f in data.expense_facts:
        if (f["cost_centre_id"] == office_id
                and f.get("expense_type") == EXPENSE_TYPE_INDIRECT
                and f["period"] in pool_by_period):
            pool_by_period[f["period"]] += f["amount"]

    # Office-home employees' salary also feeds the overhead pool (v0.3.82):
    # staff whose home cost centre is Office are pure overhead, so their pay
    # is spread across the partner teams rather than shown as their own
    # salary line. Their pay still lands on Office as Salary in the labour
    # facts; the pool + a negative offset on Office redistribute it.
    office_salary_by_period: dict[str, float] = {p: 0.0 for p in periods}
    for r in sal_amt_rows:
        p = r["period"]
        if p not in office_salary_by_period:
            continue
        key = emp_key(r["employee_name"])
        # Location-excluded office staff don't feed the pool — their salary
        # stays as an Office cost instead of being spread to partner teams.
        if not included(key):
            _note_excluded(key, r["employee_name"])
            continue
        if home_cc(p, key) != office_id:
            continue
        amt = float(r["salary_paid"] or 0.0)
        if options.include_reimbursement:
            amt += float(r["reimbursement"] or 0.0)
        office_salary_by_period[p] += amt

    for p in periods:
        prev_p = prev_map[p]
        cur = roster.get(p, {})
        prev = roster.get(prev_p, {})
        has_prev = bool(prev)
        active = []
        for key, name in sorted(cur.items(), key=lambda kv: kv[1].lower()):
            cc_id = home_cc(p, key)
            active.append({
                "key": key, "name": name,
                "cost_centre_id": cc_id, "cc_code": cc_code(cc_id),
                "location": loc_name(key),
                # Movement is only meaningful when we actually hold the
                # previous month's timesheet — otherwise EVERYONE would
                # read as a "new joiner" on the first ever import.
                "is_new": has_prev and key not in prev,
            })
        exits = []
        if has_prev:
            for key, name in sorted(prev.items(), key=lambda kv: kv[1].lower()):
                if key in cur:
                    continue
                cc_id = home_cc(prev_p, key)
                exits.append({
                    "key": key, "name": name,
                    "cost_centre_id": cc_id, "cc_code": cc_code(cc_id),
                    "location": loc_name(key),
                })
        n = len(active)
        # Overhead recipients = active employees whose home CC is a PARTNER
        # (office-home staff are the cost SOURCE, not recipients, v0.3.82)
        # PLUS the partners themselves (v0.3.98) — partners aren't in the
        # employee master but each active partner is one overhead head.
        recipients = (sum(1 for a in active if a["cost_centre_id"] != office_id)
                      + len(partners))
        office_indirect = round(pool_by_period.get(p, 0.0), 2)
        office_salary = round(office_salary_by_period.get(p, 0.0), 2)
        pool = round(office_indirect + office_salary, 2)
        per_emp = round(pool / recipients, 2) if recipients and pool > 0 else 0.0
        data.employee_register.append({
            "period": p,
            "prev_period": prev_p,
            "has_prev_data": has_prev,
            "active": active,
            "exits": exits,
            "partners": partners,
            "active_count": n,
            "new_count": sum(1 for a in active if a["is_new"]),
            "exit_count": len(exits),
            "office_indirect": office_indirect,
            "office_salary": office_salary,
            "recipients_count": recipients,
            "pool": pool,
            "per_employee": per_emp,
        })
        if pool > 0 and recipients == 0:
            data.warnings.append(
                f"{month_label(p)}: office overhead pool of {pool:,.0f} "
                f"could not be allocated — no active partner-team "
                f"employees in the period.")

    # Tagging gaps: employees dropped ONLY because they carry no location.
    if excluded_untagged:
        shown = sorted(excluded_untagged)
        names = ", ".join(shown[:8])
        more = len(shown) - 8
        data.warnings.append(
            f"{len(shown)} employee(s) with NO location assigned were left "
            f"out of the Employee Register / overhead: {names}"
            + (f" (+{more} more)" if more > 0 else "")
            + ". Assign locations in Master Data ▸ Employees (or resolve "
              "raw names in Review & Map) to include them.")

    # Tagging gaps: partners dropped ONLY because they carry no location
    # (v0.3.104). A wrong-location partner is excluded silently (filter
    # working as intended); an untagged one is a setup gap worth flagging.
    if excluded_partners_untagged:
        shown = sorted(excluded_partners_untagged)
        names = ", ".join(shown[:8])
        more = len(shown) - 8
        data.warnings.append(
            f"{len(shown)} partner(s) with NO location assigned were left "
            f"out of the office-overhead recipients: {names}"
            + (f" (+{more} more)" if more > 0 else "")
            + ". Assign locations in Master Data ▸ Cost Centres to include "
              "them.")


def _build_client_register(data: MISData, options: MISOptions,
                            masters: dict) -> None:
    """Client analogue of the employee register: who was billed each period,
    and which clients are NEW (billed for the first time ever), grouped by
    cost centre.

    "Billed" = the client appears on a sales voucher in the period (resolved
    ``client_id``). A client is **new** only in the period of their
    first-ever billing across ALL history the system holds — clients bill
    irregularly, so a month's absence does NOT mean they're lost, and the
    system keeps remembering every past client. There is therefore no
    "lost" concept; only additions are flagged.
    """
    clients = masters["clients"]
    cost_centres = masters["cost_centres"]

    periods = sorted(options.periods)
    ph = _placeholders(periods)
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT period, client_id FROM vouchers "
            f"WHERE kind = 'sales' AND client_id IS NOT NULL "
            f"AND period IN ({ph})",
            periods).fetchall()
        # First-ever billing month per client across ALL history (no period
        # filter) — a client counts as "new" only in that month.
        first_rows = conn.execute(
            "SELECT client_id, MIN(period) AS first_period FROM vouchers "
            "WHERE kind = 'sales' AND client_id IS NOT NULL AND period <> '' "
            "GROUP BY client_id").fetchall()
    first_billed = {r["client_id"]: r["first_period"] for r in first_rows}

    billed: dict[str, set] = {p: set() for p in periods}
    for r in rows:
        billed.setdefault(r["period"], set()).add(r["client_id"])

    def cc_code(cc_id):
        return (cost_centres.get(cc_id) or {}).get("code") or "—"

    def info(cid):
        cl = clients.get(cid) or {}
        cc_id = cl.get("cost_centre_id")
        return {"client_id": cid,
                "name": cl.get("canonical_name") or f"Client #{cid}",
                "cost_centre_id": cc_id, "cc_code": cc_code(cc_id)}

    def name_key(cid):
        return ((clients.get(cid) or {}).get("canonical_name") or "").lower()

    for p in periods:
        active = []
        for cid in sorted(billed.get(p, set()), key=name_key):
            rec = info(cid)
            rec["is_new"] = (first_billed.get(cid) == p)
            active.append(rec)
        data.client_register.append({
            "period": p,
            "active": active,
            "active_count": len(active),
            "new_count": sum(1 for a in active if a["is_new"]),
        })


# --- labour facts ------------------------------------------------------------

def _build_labour_facts(data: MISData, options: MISOptions, masters: dict) -> None:
    """Build per-(employee, client/CC) salary-cost facts for the period.

    Each employee's monthly salary (+ optional ``reimbursement``) is
    divided by ``days_in_month * 8`` to get an hourly rate (the firm's
    standard month-hours, not actual timesheet hours — so an
    under-filled timesheet doesn't inflate the rate). Each timesheet
    line then books ``hours × rate`` against the client's cost centre.

    Any residual hours (``standard_month_hours - sum(timesheet_hours)``,
    if positive) are booked to the employee's home cost centre
    (``employees.default_cost_centre_id``, fallback to the salary
    sheet's CC, fallback to Office) so the FULL monthly cost lands
    somewhere — no labour cost silently vanishes.

    Office overhead facts ride on the employee register built by
    :func:`_build_employee_register`: every ACTIVE employee (filed
    timesheet hours that period) carries one ``is_overhead=True`` fact
    of ``office indirect pool ÷ active count`` on their home cost
    centre, plus a single negative offset fact on Office so the pool —
    which already sits in Office's direct expenses — isn't counted
    twice. (Replaces the ``fixed_office_overhead`` master, v0.3.69.)
    """
    import calendar
    office_id = masters["office_id"]
    clients = masters["clients"]
    emp_index = masters["emp_index"]
    employees = masters["employees"]
    managers = masters["managers"]
    locations = masters["locations"]
    included = _location_filter(masters, options)
    ph = _placeholders(options.periods)

    def emp_location(key) -> str:
        """Display name of the employee's location ('—' when untagged)."""
        if not isinstance(key, int):
            return "—"
        loc_id = (employees.get(key) or {}).get("location_id")
        return (locations.get(loc_id) or {}).get("name") or "—"

    def manager_for(emp_lookup_key, charged_cc):
        """The employee's assigned manager — but only when that manager
        belongs to the cost centre the cost is charged to, so a manager
        only ever appears under their own partner block in the
        Partner-Manager P&L. Cross-partner billable work (charged to a
        different partner) falls to that partner's 'Self' column. A
        deactivated manager folds into the partner (returns None) so the
        MIS shows the partner total without the manager breakdown."""
        if not isinstance(emp_lookup_key, int):
            return None
        m = (employees.get(emp_lookup_key) or {}).get("manager_id")
        if m is None:
            return None
        mrec = managers.get(m) or {}
        if not mrec.get("active", 1):
            return None
        if mrec.get("cost_centre_id") == charged_cc:
            return m
        return None

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
        std_hours = standard_hours(period)
        # SALARY rate uses salary alone (NOT salary + overhead). v0.3.57
        # baked them together which let overhead bifurcate across whichever
        # partner's client the employee worked on. v0.3.67 separates the
        # two: salary still bifurcates by timesheet (rate × hours per
        # client's CC), overhead is a flat per-employee cost that lands
        # entirely on the employee's home CC.
        salary_rate = rec["amount"] / std_hours if std_hours else 0.0

        # Home CC: master record → fallback to salary's CC → Office.
        home_cc = rec["fallback_cc"]
        if isinstance(emp_lookup_key, int):
            home_cc = (employees.get(emp_lookup_key) or {}).get(
                "default_cost_centre_id") or home_cc
        home_cc = home_cc or office_id

        # Office-home employees are pure overhead (v0.3.82): ALL of their
        # cost lands on Office regardless of which client they booked, and
        # their pay is redistributed to the partner teams via the pool.
        emp_is_office_home = (home_cc == office_id)
        # Pool source (v0.3.98): this employee's salary rows feed the
        # overhead pool — flagged so the Employee Register's Office Staff
        # Salary column can SUMIFS them live off the Salary sheet. Only
        # office-home staff within the selected locations qualify (must
        # mirror the register's office_salary_by_period computation).
        is_pool_source = emp_is_office_home and included(emp_lookup_key)
        location = emp_location(emp_lookup_key)

        if total_logged > 0:
            for t in rows:
                h = float(t["hours"] or 0.0)
                if not h:
                    continue
                # Client's own CC — only for billable rows whose client
                # master row has a real (non-Office) cost centre.
                client_cc = None
                if t["is_billable"] and t["client_id"] is not None:
                    client = clients.get(t["client_id"])
                    if (client and client["cost_centre_id"] is not None
                            and client["cost_centre_id"] != office_id):
                        client_cc = client["cost_centre_id"]
                # Attribution + billable flag:
                #  • office-home staff  → Office (non-billable)
                #  • billable on a real client → that client's partner CC
                #  • everything else (non-billable, office client, no CC)
                #    → the employee's HOME partner CC, NON-billable. This
                #    is the v0.3.82 fix: office-booked time by a partner's
                #    employee now lands on their home CC, not Office.
                if emp_is_office_home:
                    cc, billable = office_id, False
                elif client_cc is not None:
                    cc, billable = client_cc, True
                else:
                    cc, billable = home_cc, False
                data.labour_facts.append({
                    "period": period,
                    "txn_date": t["txn_date"],
                    "cost_centre_id": cc,
                    "manager_id": manager_for(emp_lookup_key, cc),
                    "home_cost_centre_id": home_cc,
                    "client_cost_centre_id": client_cc if billable else None,
                    "employee_name": rec["name"],
                    "client_id": t["client_id"],
                    "client_raw": t["client_raw"],
                    "is_residual": False,
                    "is_overhead": False,
                    "is_pool_source": is_pool_source,
                    "location": location,
                    "billable": billable,
                    "hours": h, "amount": h * salary_rate,
                })
            residual = std_hours - total_logged
            if residual > 0.01 and salary_rate > 0:
                data.labour_facts.append({
                    "period": period,
                    "txn_date": None,
                    "cost_centre_id": home_cc,
                    "manager_id": manager_for(emp_lookup_key, home_cc),
                    "home_cost_centre_id": home_cc,
                    "client_cost_centre_id": None,
                    "employee_name": rec["name"],
                    "client_id": None,
                    "client_raw": None,
                    "is_residual": True,
                    "is_overhead": False,
                    "is_pool_source": is_pool_source,
                    "location": location,
                    # Residual / unallocated time counts as billable
                    # (operator decision, v0.3.89) — except for office-home
                    # staff, whose cost is pure overhead either way.
                    "billable": not emp_is_office_home,
                    "hours": residual, "amount": residual * salary_rate,
                })
        elif rec["amount"]:
            data.labour_facts.append({
                "period": period,
                "txn_date": None,
                "cost_centre_id": home_cc,
                "manager_id": manager_for(emp_lookup_key, home_cc),
                "home_cost_centre_id": home_cc,
                "client_cost_centre_id": None,
                "employee_name": rec["name"],
                "client_id": None,
                "client_raw": None,
                "is_residual": True,
                "is_overhead": False,
                "is_pool_source": is_pool_source,
                "location": location,
                # No timesheet at all → the whole salary is residual;
                # treat as billable (v0.3.89) unless office-home.
                "billable": not emp_is_office_home,
                "hours": std_hours, "amount": rec["amount"],
            })

    # --- office overhead: per ACTIVE employee, from the employee register.
    # The per-head share (office indirect pool ÷ active count) lands on
    # each active employee's home cost centre; one negative offset fact
    # on Office backs the pool out of the office bucket (the pool's
    # source rows already sit in Office's direct expenses, and the CC
    # P&L shows them there — without the offset the same rupees would
    # appear twice in the firm total).
    for reg in data.employee_register:
        per_emp = reg["per_employee"]
        recipients = reg["recipients_count"]
        if per_emp <= 0 or recipients <= 0:
            continue
        period = reg["period"]
        # Recipients: partner-team active employees + the partners
        # themselves (v0.3.98). Office-home staff are the source of
        # (part of) the pool, not recipients.
        heads = ([e for e in reg["active"]
                  if e["cost_centre_id"] != office_id]
                 + reg.get("partners", []))
        for emp in heads:
            data.labour_facts.append({
                "period": period,
                "txn_date": None,
                "cost_centre_id": emp["cost_centre_id"],
                "home_cost_centre_id": emp["cost_centre_id"],
                "client_cost_centre_id": None,
                "employee_name": emp["name"],
                "client_id": None,
                "client_raw": None,
                "is_residual": False,
                "is_overhead": True,
                "is_overhead_offset": False,
                "location": emp.get("location", "—"),
                "billable": False,
                "hours": 0.0, "amount": per_emp,
            })
        # Negative offset on Office backs the whole pool (office indirect +
        # office-home salary) out of the Office bucket — it's redistributed
        # to the partner teams above.
        data.labour_facts.append({
            "period": period,
            "txn_date": None,
            "cost_centre_id": office_id,
            "home_cost_centre_id": office_id,
            "client_cost_centre_id": None,
            "employee_name": "(Office overhead allocated to partner teams)",
            "client_id": None,
            "client_raw": None,
            "is_residual": False,
            "is_overhead": True,
            "is_overhead_offset": True,
            "location": "—",
            "billable": False,
            "hours": 0.0,
            "amount": -round(per_emp * recipients, 2),
        })


def _build_reimbursement_facts(data: MISData, options: MISOptions,
                                masters: dict) -> None:
    """Build one fact per uploaded reimbursement row.

    Each fact's cost-centre is the CLIENT'S cost centre from the master
    (the partner who serves that client bears the cost). When the
    client_id hasn't been resolved yet (raw text not matched to master),
    the fact falls back to the employee's home cost centre — same chain
    the labour facts use, so it doesn't silently land on Office.

    Whether the firm recovers the cost from the client (the
    ``client_reimbursable`` flag) is preserved on the fact but does
    NOT change the expense booking. The corresponding recovery
    appears on the revenue side via the Sales Register's
    Reimbursement / OPE ledger lines — the partner P&L nets the wash
    naturally without us double-handling here.
    """
    if not options.periods:
        return
    clients = masters["clients"]
    employees = masters["employees"]
    emp_index = masters["emp_index"]
    office_id = masters["office_id"]
    fold_mgr = _mgr_folder(masters)
    ph = _placeholders(options.periods)
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT period, txn_date, employee_name, client_id, "
            f"       client_raw, amount, client_reimbursable "
            f"FROM reimbursements "
            f"WHERE period IN ({ph})",
            options.periods).fetchall()
    for r in rows:
        client = clients.get(r["client_id"])
        # The EMPLOYEE's home cost centre (from the master) — shown on the
        # Reimbursements sheet; also the booking-CC fallback when the
        # client isn't mapped.
        emp_id = emp_index.get(norm(r["employee_name"]))
        emp_rec = employees.get(emp_id) if isinstance(emp_id, int) else None
        emp_cc = (emp_rec or {}).get("default_cost_centre_id")
        # Fold a deactivated manager to None so the Reimbursements sheet's
        # Manager column matches the rest of the MIS (v0.3.97).
        emp_mgr = fold_mgr((emp_rec or {}).get("manager_id"))
        # Booking CC: client's partner bears the cost; fall back to the
        # employee's home CC, then Office.
        cc = (client["cost_centre_id"] if client else None) or emp_cc \
            or office_id
        data.reimbursement_facts.append({
            "period": r["period"],
            "txn_date": r["txn_date"],
            "cost_centre_id": cc,
            "employee_cost_centre_id": emp_cc,
            "employee_manager_id": emp_mgr,
            "employee_name": r["employee_name"],
            "client_id": r["client_id"],
            "client_raw": r["client_raw"],
            "client_reimbursable": bool(r["client_reimbursable"]),
            "amount": float(r["amount"] or 0.0),
        })


def _build_provision_facts(data: MISData, options: MISOptions,
                            masters: dict) -> None:
    """Build one fact per OUTSTANDING provision, carried forward to the
    reporting month.

    A provision booked in month P is an expected direct cost on its
    client's cost centre. It shows in the MIS for every month from P
    onward (``carry forward``) at its REMAINING value — original amount
    minus the adjustments recorded up to and including the reporting
    month — until that remaining reaches zero. The fact is stamped with
    the latest selected period so it lands once in the current MIS,
    regardless of how many months are selected.
    """
    if not options.periods:
        return
    clients = masters["clients"]
    entities = masters["entities"]
    max_p = max(options.periods)
    with transaction() as conn:
        provs = [dict(r) for r in conn.execute(
            "SELECT * FROM provisions WHERE active = 1")]
        adjs = conn.execute(
            "SELECT provision_id, amount, adjusted_period "
            "FROM provision_adjustments").fetchall()
    adj_by: dict[int, list] = {}
    for a in adjs:
        adj_by.setdefault(a["provision_id"], []).append(a)
    for p in provs:
        # Not yet booked as of the reporting month (string compare is safe
        # for 'YYYY-MM').
        if (p["period"] or "") > max_p:
            continue
        adjusted = sum(
            float(a["amount"] or 0.0) for a in adj_by.get(p["id"], [])
            if (a["adjusted_period"] or "") <= max_p)
        remaining = round(float(p["amount"] or 0.0) - adjusted, 2)
        if remaining <= 0.005:
            continue
        client = clients.get(p["client_id"])
        cc_id = client["cost_centre_id"] if client else None
        data.provision_facts.append({
            "period": max_p,
            "provision_period": p["period"],
            "cost_centre_id": cc_id,
            "entity_id": p["entity_id"],
            "client_id": p["client_id"],
            "client_name": (client or {}).get("canonical_name"),
            "entity_name": (entities.get(p["entity_id"]) or {}).get("name"),
            "original": round(float(p["amount"] or 0.0), 2),
            "adjusted": round(adjusted, 2),
            "amount": remaining,
        })


# --- roll-ups ----------------------------------------------------------------

def _roll_up(data: MISData, masters: dict) -> None:
    cost_centres = masters["cost_centres"]
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

    # Revenue splits into sales income vs reimbursement/OPE recovery
    # (v0.3.89) so the Cost Centre P&L can show them in separate columns.
    for f in data.revenue_facts:
        line = line_for(f["cost_centre_id"])
        if f.get("category") in ("Reimbursement", "OPE"):
            line.reimbursement_income += f["amount"]
        else:
            line.revenue += f["amount"]
    for f in data.expense_facts:
        line_for(f["cost_centre_id"]).direct_expense += f["amount"]
    for f in data.labour_facts:
        # Overhead facts (incl. the negative Office offset) live in the
        # Allocated Overhead column; pure salary stays in Salary Cost.
        # Mirrors the workbook's Type="Salary"/"Overhead" SUMIFS split.
        if f.get("is_overhead"):
            line_for(f["cost_centre_id"]).allocated_overhead += f["amount"]
        else:
            line_for(f["cost_centre_id"]).labour += f["amount"]
    # Reimbursement-sheet outlays get their OWN cost column (v0.3.89). When
    # client_reimbursable=YES the matching recovery comes through the Sales
    # Register as a Reimbursement/OPE ledger (reimbursement_income above),
    # so the partner's net is washed; when NO the firm absorbs the cost.
    for f in data.reimbursement_facts:
        line_for(f["cost_centre_id"]).reimbursement_expense += f["amount"]
    # Outstanding provisions are a direct cost on the client's cost centre.
    for f in data.provision_facts:
        line_for(f["cost_centre_id"]).direct_expense += f["amount"]

    # Targets (annual, pro-rated to the number of months selected).
    # Match on the NORMALISED financial year — the operator may have typed
    # '2026 - 27' etc. in the master, which never equalled the tight
    # '2026-27' financial_year() emits, so targets silently read 0.
    fys = {financial_year(p) for p in options.periods}
    months = len(options.periods)
    with transaction() as conn:
        stored: dict[tuple[str, int], float] = {}
        for row in conn.execute(
                "SELECT financial_year, cost_centre_id, target_amount "
                "FROM targets"):
            stored[(normalize_fy(row["financial_year"]),
                    row["cost_centre_id"])] = float(row["target_amount"])
        for cc_id, line in lines.items():
            if cc_id is None:
                continue
            total = 0.0
            for fy in fys:
                amt = stored.get((normalize_fy(fy), cc_id))
                if amt is not None:
                    total += amt / 12.0 * months
            line.target = total

    # Office overhead is already allocated per active employee via the
    # is_overhead labour facts (with the negative offset on Office) — the
    # old mode-based allocator (separate / revenue / equal) is gone.
    data.cost_centres = sorted(
        lines.values(),
        key=lambda l: (l.is_office, l.cost_centre_id is not None and 0 or 1,
                       -l.revenue))
    _roll_up_dimensions(data, masters)


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
            # No manager (partner's own work, or a deactivated manager folded
            # in) → label with just the partner code, so a partner with no
            # active managers reads as "PM" rather than "PM – (unassigned)".
            if mgr_id is None:
                label = cc_code
            else:
                mgr_code = mgr.get(mgr_id, {}).get("code", "(unassigned)")
                label = f"{cc_code} – {mgr_code}"
            pm[key] = {"label": label,
                       "cost_centre_id": cc_id, "manager_id": mgr_id,
                       "revenue": 0.0, "direct_expense": 0.0}
        return pm[key]

    for f in data.revenue_facts:
        pm_line(f["cost_centre_id"], f["manager_id"])["revenue"] += f["amount"]
    for f in data.expense_facts:
        pm_line(f["cost_centre_id"], f["manager_id"])["direct_expense"] += f["amount"]
    # Provisions carry no manager — attribute to the partner's "Self" column.
    for f in data.provision_facts:
        pm_line(f["cost_centre_id"], None)["direct_expense"] += f["amount"]
    data.partner_manager = sorted(pm.values(), key=lambda d: -d["revenue"])

    # Entity.
    ent_agg: dict = {}
    for f in data.revenue_facts:
        e = ent_agg.setdefault(f["entity_id"], {"revenue": 0.0, "direct_expense": 0.0})
        e["revenue"] += f["amount"]
    for f in data.expense_facts:
        e = ent_agg.setdefault(f["entity_id"], {"revenue": 0.0, "direct_expense": 0.0})
        e["direct_expense"] += f["amount"]
    for f in data.provision_facts:
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
