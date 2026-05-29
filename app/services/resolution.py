"""Name-resolution service: link raw client / employee names to master records.

Tally and the timesheet spell the same client differently ("XYZ Corporate" vs
"XYZ Corporate Pvt Ltd"); the timesheet and salary sheet spell employees
differently too. The operator confirms a match once and it is remembered as an
alias, so future imports resolve automatically.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from ..database import transaction

# --- normalisation -----------------------------------------------------------

_COMPANY_NOISE = (
    "private limited", "pvt ltd", "pvt. ltd.", "pvt", "limited", "ltd",
    "llp", "& co", "and co", "co.", "corporation", "inc",
)


def norm(text: str | None) -> str:
    """Lower-case, collapse whitespace — used for exact comparisons."""
    return " ".join((text or "").strip().lower().split())


def norm_loose(text: str | None) -> str:
    """Aggressively normalised form (drops company suffixes) — for fuzzy match."""
    out = norm(text)
    for noise in _COMPANY_NOISE:
        out = out.replace(noise, "")
    return " ".join(out.split())


# =========================== CLIENTS ========================================

def _apply_client_norm_mapping(conn, name_to_cid: dict[str, int]) -> int:
    """Set vouchers.client_id / timesheet_entries.client_id wherever the
    Python-normalised raw name matches a key in *name_to_cid*.

    SQL ``LOWER(TRIM(...))`` doesn't collapse internal whitespace — Tally
    sometimes writes multiple spaces in client names, which used to leave
    rows unmapped even after the operator confirmed them. Matching in Python
    via :func:`norm` (which collapses any run of whitespace) fixes that.
    """
    linked = 0
    rows = conn.execute(
        "SELECT id, party_name FROM vouchers "
        "WHERE kind='sales' AND client_id IS NULL "
        "AND party_name <> ''").fetchall()
    for r in rows:
        cid = name_to_cid.get(norm(r["party_name"]))
        if cid is not None:
            conn.execute("UPDATE vouchers SET client_id = ? WHERE id = ?",
                         (cid, r["id"]))
            linked += 1
    rows = conn.execute(
        "SELECT id, client_raw FROM timesheet_entries "
        "WHERE client_id IS NULL AND client_raw <> ''").fetchall()
    for r in rows:
        cid = name_to_cid.get(norm(r["client_raw"]))
        if cid is not None:
            conn.execute("UPDATE timesheet_entries SET client_id = ? WHERE id = ?",
                         (cid, r["id"]))
            linked += 1
    return linked


def apply_known_client_aliases() -> int:
    """Auto-link unresolved rows whose raw name matches a known client/alias.

    Also infers client → cost-centre links from the freshly-linked vouchers.
    """
    with transaction() as conn:
        pairs: dict[str, int] = {}
        for r in conn.execute("SELECT id, canonical_name FROM clients"):
            pairs[norm(r["canonical_name"])] = r["id"]
        for r in conn.execute(
                "SELECT client_id, alias_text FROM client_aliases"):
            pairs[norm(r["alias_text"])] = r["client_id"]
        linked = _apply_client_norm_mapping(conn, pairs)
    infer_all_masters()
    return linked


def unresolved_clients() -> list[dict]:
    """Distinct raw client names not yet linked, with their source and counts."""
    with transaction() as conn:
        agg: dict[str, dict] = {}
        for r in conn.execute(
                "SELECT party_name AS raw, COUNT(*) AS n FROM vouchers "
                "WHERE kind = 'sales' AND client_id IS NULL "
                "AND party_name <> '' GROUP BY lower(trim(party_name))"):
            _bump(agg, r["raw"], "Sales", r["n"])
        for r in conn.execute(
                "SELECT client_raw AS raw, COUNT(*) AS n FROM timesheet_entries "
                "WHERE client_id IS NULL AND client_raw <> '' "
                "GROUP BY lower(trim(client_raw))"):
            _bump(agg, r["raw"], "Timesheet", r["n"])
    return sorted(agg.values(), key=lambda d: -d["count"])


def client_suggestions(raw: str, limit: int = 6) -> list[tuple[int, str, int]]:
    """Fuzzy-rank existing clients for a raw name → (id, name, score)."""
    with transaction() as conn:
        clients = [(r["id"], r["canonical_name"])
                   for r in conn.execute(
                       "SELECT id, canonical_name FROM clients WHERE active = 1")]
    if not clients:
        return []
    target = norm_loose(raw)
    scored = process.extract(
        target, {cid: norm_loose(name) for cid, name in clients},
        scorer=fuzz.token_sort_ratio, limit=limit)
    names = dict(clients)
    return [(cid, names[cid], int(score)) for _match, score, cid in scored]


def link_client(raw: str, client_id: int) -> int:
    """Link a raw name to an existing client and remember it as an alias."""
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO client_aliases (client_id, alias_text, source) "
            "VALUES (?, ?, 'tally')", (client_id, raw))
        n = _link_client_rows(conn, raw, client_id)
    infer_all_masters()
    return n


def create_client(raw: str, canonical_name: str,
                   cost_centre_id: int | None) -> int:
    """Create a new client from a raw name and link all matching rows."""
    # If the operator didn't pick a cost centre, use the one we can infer from
    # the underlying sales vouchers.
    if cost_centre_id is None:
        cost_centre_id = suggest_cc_for_raw_client(raw)
    with transaction() as conn:
        cid = conn.execute(
            "INSERT INTO clients (canonical_name, cost_centre_id) VALUES (?, ?)",
            (canonical_name, cost_centre_id)).lastrowid
        if norm(raw) != norm(canonical_name):
            conn.execute(
                "INSERT OR IGNORE INTO client_aliases (client_id, alias_text, source) "
                "VALUES (?, ?, 'tally')", (cid, raw))
        _link_client_rows(conn, raw, cid)
    return int(cid)


def _link_client_rows(conn, raw: str, client_id: int) -> int:
    """Set client_id on all rows whose raw name normalises to *raw*."""
    return _apply_client_norm_mapping(conn, {norm(raw): client_id})


def infer_client_cost_centres() -> int:
    """For every client without a cost centre, set it to the dominant cost
    centre seen on its sales voucher splits.

    Tally's Sales Register carries the partner ("Cost Center" column) right
    next to the client name. Once the operator has mapped those cost-centre
    strings to partners, we can flow that information into the clients master
    so the operator doesn't have to set it manually on every client.

    Returns the number of clients updated. Existing cost-centre assignments
    are never overwritten.
    """
    updated = 0
    with transaction() as conn:
        rows = conn.execute(
            "SELECT c.id, "
            "  (SELECT s.cost_centre_id "
            "     FROM voucher_splits s "
            "     JOIN vouchers v ON v.id = s.voucher_id "
            "     WHERE v.kind = 'sales' AND v.client_id = c.id "
            "       AND s.cost_centre_id IS NOT NULL "
            "     GROUP BY s.cost_centre_id "
            "     ORDER BY COUNT(*) DESC LIMIT 1) AS suggested "
            "FROM clients c "
            "WHERE c.cost_centre_id IS NULL AND c.active = 1").fetchall()
        for r in rows:
            if r["suggested"] is not None:
                conn.execute(
                    "UPDATE clients SET cost_centre_id = ? WHERE id = ?",
                    (r["suggested"], r["id"]))
                updated += 1
    return updated


def infer_employee_cost_centres() -> int:
    """For every employee without a default cost centre, set it to the
    dominant cost centre seen on their salary rows (matching by name +
    aliases, whitespace-insensitive)."""
    updated = 0
    with transaction() as conn:
        emp_lookup: dict[str, int] = {
            norm(e["name"]): e["id"]
            for e in conn.execute(
                "SELECT id, name FROM employees "
                "WHERE default_cost_centre_id IS NULL AND active = 1")}
        if not emp_lookup:
            return 0
        ids = set(emp_lookup.values())
        for a in conn.execute(
                "SELECT employee_id, alias_text FROM employee_aliases"):
            if a["employee_id"] in ids:
                emp_lookup[norm(a["alias_text"])] = a["employee_id"]

        counts: dict[int, dict[int, int]] = {}
        for r in conn.execute(
                "SELECT employee_name, cost_centre_id FROM salary_entries "
                "WHERE cost_centre_id IS NOT NULL AND employee_name <> ''"):
            eid = emp_lookup.get(norm(r["employee_name"]))
            if eid is not None:
                bucket = counts.setdefault(eid, {})
                bucket[r["cost_centre_id"]] = bucket.get(r["cost_centre_id"], 0) + 1
        for eid, cc_counts in counts.items():
            dominant = max(cc_counts, key=cc_counts.get)
            conn.execute(
                "UPDATE employees SET default_cost_centre_id = ? WHERE id = ?",
                (dominant, eid))
            updated += 1
    return updated


def infer_employee_managers() -> int:
    """For every employee without a manager, infer the manager from the
    dominant Reporting Manager column on their timesheet entries — only when
    that name fuzzy-matches a manager already in the master list."""
    updated = 0
    with transaction() as conn:
        mgr_lookup: dict[str, int] = {
            norm(m["name"]): m["id"]
            for m in conn.execute(
                "SELECT id, name FROM managers WHERE active = 1")}
        if not mgr_lookup:
            return 0

        emp_lookup: dict[str, int] = {
            norm(e["name"]): e["id"]
            for e in conn.execute(
                "SELECT id, name FROM employees "
                "WHERE manager_id IS NULL AND active = 1")}
        if not emp_lookup:
            return 0
        ids = set(emp_lookup.values())
        for a in conn.execute(
                "SELECT employee_id, alias_text FROM employee_aliases"):
            if a["employee_id"] in ids:
                emp_lookup[norm(a["alias_text"])] = a["employee_id"]

        counts: dict[int, dict[int, int]] = {}
        for r in conn.execute(
                "SELECT emp_name, reporting_manager FROM timesheet_entries "
                "WHERE reporting_manager <> '' AND emp_name <> ''"):
            eid = emp_lookup.get(norm(r["emp_name"]))
            mid = mgr_lookup.get(norm(r["reporting_manager"]))
            if eid is None or mid is None:
                continue
            bucket = counts.setdefault(eid, {})
            bucket[mid] = bucket.get(mid, 0) + 1
        for eid, mgr_counts in counts.items():
            dominant = max(mgr_counts, key=mgr_counts.get)
            conn.execute(
                "UPDATE employees SET manager_id = ? WHERE id = ?",
                (dominant, eid))
            updated += 1
    return updated


def infer_manager_cost_centres() -> int:
    """For every manager without a cost centre, take the dominant cost centre
    of the employees who report to them."""
    updated = 0
    with transaction() as conn:
        rows = conn.execute(
            "SELECT m.id, "
            "  (SELECT e.default_cost_centre_id "
            "     FROM employees e "
            "     WHERE e.manager_id = m.id "
            "       AND e.default_cost_centre_id IS NOT NULL "
            "     GROUP BY e.default_cost_centre_id "
            "     ORDER BY COUNT(*) DESC LIMIT 1) AS suggested "
            "FROM managers m "
            "WHERE m.cost_centre_id IS NULL AND m.active = 1").fetchall()
        for r in rows:
            if r["suggested"] is not None:
                conn.execute(
                    "UPDATE managers SET cost_centre_id = ? WHERE id = ?",
                    (r["suggested"], r["id"]))
                updated += 1
    return updated


def infer_all_masters() -> dict[str, int]:
    """Run every auto-inference pass over the masters. Idempotent, cheap, and
    safe to call after any operator action or import.

    Order matters: employee cost-centres come from salary; employee managers
    come from timesheet; manager cost-centres come from their employees; and
    client cost-centres come from sales voucher splits."""
    return {
        "employees_cc": infer_employee_cost_centres(),
        "employees_mgr": infer_employee_managers(),
        "managers_cc": infer_manager_cost_centres(),
        "clients_cc": infer_client_cost_centres(),
    }


def suggest_cc_for_raw_client(raw: str) -> int | None:
    """Return the dominant cost-centre id seen on sales vouchers whose party
    matches *raw*, or ``None``. Used to pre-fill the resolve dialog."""
    if not raw:
        return None
    key = norm(raw)
    with transaction() as conn:
        # Pull all matching vouchers in Python so whitespace differences in
        # party_name don't kill the match.
        rows = conn.execute(
            "SELECT v.id, v.party_name "
            "FROM vouchers v WHERE v.kind = 'sales' "
            "AND v.party_name <> ''").fetchall()
        ids = [r["id"] for r in rows if norm(r["party_name"]) == key]
        if not ids:
            return None
        ph = ",".join("?" * len(ids))
        row = conn.execute(
            f"SELECT s.cost_centre_id, COUNT(*) AS n "
            f"FROM voucher_splits s "
            f"WHERE s.voucher_id IN ({ph}) "
            f"AND s.cost_centre_id IS NOT NULL "
            f"GROUP BY s.cost_centre_id ORDER BY n DESC LIMIT 1",
            ids).fetchone()
    return row["cost_centre_id"] if row else None


def bulk_create_clients() -> int:
    """Create a client master record for every still-unresolved raw name.

    Cost centre is inferred from the underlying sales vouchers when possible;
    otherwise it's left unassigned and the operator can set it later in
    Master Data. A one-shot escape hatch for the first big import.
    """
    count = 0
    for item in unresolved_clients():
        raw = item["raw"]
        with transaction() as conn:
            exists = conn.execute(
                "SELECT id FROM clients WHERE lower(canonical_name) = ?",
                (norm(raw),)).fetchone()
        cid = exists["id"] if exists else None
        if cid is None:
            cid = create_client(raw, raw, None)        # auto-infers CC
        else:
            link_client(raw, cid)
        count += 1
    # One more sweep — bulk-create just created N clients; any that still
    # have NULL cost centre but linked to vouchers with resolved splits
    # should pick those up.
    infer_all_masters()
    return count


# =========================== EMPLOYEES ======================================

def apply_known_employee_aliases() -> None:
    """No row updates needed — employees are matched by name at calc time —
    but this keeps the API symmetric and is a hook for future use."""
    return None


def unresolved_employees() -> list[dict]:
    """Distinct employee names from timesheet/salary with no master record."""
    with transaction() as conn:
        known: set[str] = set()
        for r in conn.execute("SELECT name FROM employees"):
            known.add(norm(r["name"]))
        for r in conn.execute("SELECT alias_text FROM employee_aliases"):
            known.add(norm(r["alias_text"]))

        agg: dict[str, dict] = {}
        for r in conn.execute(
                "SELECT emp_name AS raw, COUNT(*) AS n FROM timesheet_entries "
                "WHERE emp_name <> '' GROUP BY lower(trim(emp_name))"):
            if norm(r["raw"]) not in known:
                _bump(agg, r["raw"], "Timesheet", r["n"])
        for r in conn.execute(
                "SELECT employee_name AS raw, COUNT(*) AS n FROM salary_entries "
                "WHERE employee_name <> '' GROUP BY lower(trim(employee_name))"):
            if norm(r["raw"]) not in known:
                _bump(agg, r["raw"], "Salary", r["n"])
    return sorted(agg.values(), key=lambda d: -d["count"])


def employee_suggestions(raw: str, limit: int = 6) -> list[tuple[int, str, int]]:
    """Fuzzy-rank existing employees for a raw name → (id, name, score)."""
    with transaction() as conn:
        emps = [(r["id"], r["name"])
                for r in conn.execute(
                    "SELECT id, name FROM employees WHERE active = 1")]
    if not emps:
        return []
    scored = process.extract(
        norm(raw), {eid: norm(name) for eid, name in emps},
        scorer=fuzz.token_sort_ratio, limit=limit)
    names = dict(emps)
    return [(eid, names[eid], int(score)) for _m, score, eid in scored]


def link_employee(raw: str, employee_id: int, source: str = "timesheet") -> None:
    """Record a raw name as an alias of an existing employee."""
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO employee_aliases (employee_id, alias_text, source) "
            "VALUES (?, ?, ?)", (employee_id, raw, source))
    infer_all_masters()


def create_employee(raw: str, name: str, category: str | None,
                     manager_id: int | None,
                     cost_centre_id: int | None) -> int:
    """Create a new employee master record from a raw name."""
    with transaction() as conn:
        eid = conn.execute(
            "INSERT INTO employees (name, category, manager_id, "
            "default_cost_centre_id) VALUES (?, ?, ?, ?)",
            (name, category, manager_id, cost_centre_id)).lastrowid
        if norm(raw) != norm(name):
            conn.execute(
                "INSERT OR IGNORE INTO employee_aliases "
                "(employee_id, alias_text, source) VALUES (?, ?, 'timesheet')",
                (eid, raw))
    # If the operator didn't pick manager / cost centre, see if we can.
    infer_all_masters()
    return int(eid)


# --- shared ------------------------------------------------------------------

def bulk_create_employees() -> int:
    """Create an employee master record for every still-unresolved raw name.

    Manager and cost centre are auto-inferred from the timesheet / salary
    sheet after creation; whatever can't be inferred is left blank for the
    operator to fill in later.
    """
    count = 0
    for item in unresolved_employees():
        create_employee(item["raw"], item["raw"], "Employee", None, None)
        count += 1
    infer_all_masters()
    return count


# ====================== COST-CENTRE STRINGS ================================

def apply_known_cc_string_mappings() -> int:
    """For each saved mapping, set the cost-centre / manager on every
    voucher_split whose voucher carries the matching ``raw_cost_centre``.

    Returns the number of split rows updated. Comparison is whitespace-
    insensitive (Tally sometimes writes multiple spaces in cost-centre names).
    """
    updated = 0
    with transaction() as conn:
        mappings = {
            norm(r["raw_text"]): (r["cost_centre_id"], r["manager_id"])
            for r in conn.execute(
                "SELECT raw_text, cost_centre_id, manager_id "
                "FROM cc_string_mappings WHERE active = 1")}
        if not mappings:
            return 0
        vouchers = conn.execute(
            "SELECT id, raw_cost_centre FROM vouchers "
            "WHERE kind = 'sales' AND raw_cost_centre <> ''").fetchall()
        # Bucket voucher ids by their normalised raw_cost_centre.
        buckets: dict[str, list[int]] = {}
        for v in vouchers:
            n = norm(v["raw_cost_centre"])
            if n in mappings:
                buckets.setdefault(n, []).append(v["id"])
        for n, ids in buckets.items():
            cc_id, mgr_id = mappings[n]
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"UPDATE voucher_splits SET cost_centre_id = ?, manager_id = ? "
                f"WHERE voucher_id IN ({placeholders})",
                (cc_id, mgr_id, *ids))
            updated += cur.rowcount
    return updated


def unresolved_cc_strings() -> list[dict]:
    """Distinct ``raw_cost_centre`` strings (from sales vouchers) that have no
    saved mapping yet. Whitespace-insensitive."""
    with transaction() as conn:
        known = {norm(r["raw_text"]) for r in conn.execute(
            "SELECT raw_text FROM cc_string_mappings WHERE active = 1")}
        rows = conn.execute(
            "SELECT raw_cost_centre AS raw FROM vouchers "
            "WHERE kind = 'sales' AND raw_cost_centre <> ''").fetchall()
    agg: dict[str, dict] = {}
    for r in rows:
        n = norm(r["raw"])
        if n in known:
            continue
        entry = agg.setdefault(n, {"raw": r["raw"], "count": 0})
        entry["count"] += 1
    return sorted(agg.values(), key=lambda d: -d["count"])


def map_cc_string(raw: str, cost_centre_id: int | None,
                  manager_id: int | None) -> int:
    """Save a Cost Centre string mapping and back-apply it.

    Returns the number of voucher splits updated.
    """
    with transaction() as conn:
        conn.execute(
            "INSERT INTO cc_string_mappings (raw_text, cost_centre_id, manager_id) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(raw_text) DO UPDATE SET "
            "  cost_centre_id = excluded.cost_centre_id, "
            "  manager_id = excluded.manager_id, "
            "  active = 1",
            (raw, cost_centre_id, manager_id))
    n = apply_known_cc_string_mappings()
    # Now that cost centres are populated on splits, clients can pick them up.
    infer_all_masters()
    return n


def _bump(agg: dict[str, dict], raw: str, source: str, n: int) -> None:
    key = norm(raw)
    entry = agg.setdefault(key, {"raw": raw, "sources": set(), "count": 0})
    entry["sources"].add(source)
    entry["count"] += n
