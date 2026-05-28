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

def apply_known_client_aliases() -> int:
    """Auto-link unresolved rows whose raw name matches a known client/alias.

    Returns the number of newly linked rows.
    """
    with transaction() as conn:
        pairs: dict[str, int] = {}
        for r in conn.execute("SELECT id, canonical_name FROM clients"):
            pairs[norm(r["canonical_name"])] = r["id"]
        for r in conn.execute("SELECT client_id, alias_text FROM client_aliases"):
            pairs[norm(r["alias_text"])] = r["client_id"]

        linked = 0
        for name, cid in pairs.items():
            cur = conn.execute(
                "UPDATE vouchers SET client_id = ? "
                "WHERE kind = 'sales' AND client_id IS NULL "
                "AND lower(trim(party_name)) = ?", (cid, name))
            linked += cur.rowcount
            cur = conn.execute(
                "UPDATE timesheet_entries SET client_id = ? "
                "WHERE client_id IS NULL AND lower(trim(client_raw)) = ?",
                (cid, name))
            linked += cur.rowcount
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
    return n


def create_client(raw: str, canonical_name: str,
                   cost_centre_id: int | None) -> int:
    """Create a new client from a raw name and link all matching rows."""
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
    key = norm(raw)
    n = conn.execute(
        "UPDATE vouchers SET client_id = ? WHERE kind = 'sales' "
        "AND client_id IS NULL AND lower(trim(party_name)) = ?",
        (client_id, key)).rowcount
    n += conn.execute(
        "UPDATE timesheet_entries SET client_id = ? "
        "WHERE client_id IS NULL AND lower(trim(client_raw)) = ?",
        (client_id, key)).rowcount
    return n


def bulk_create_clients() -> int:
    """Create a client master record for every still-unresolved raw name.

    Cost centre is left unassigned — the operator sets it later in Master Data
    or the Vouchers tab. A one-time escape hatch for the first big import.
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
            cid = create_client(raw, raw, None)
        else:
            link_client(raw, cid)
        count += 1
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
    return int(eid)


# --- shared ------------------------------------------------------------------

def bulk_create_employees() -> int:
    """Create an employee master record for every still-unresolved raw name.

    Manager and cost centre are left blank for the operator to fill in later.
    """
    count = 0
    for item in unresolved_employees():
        create_employee(item["raw"], item["raw"], "Employee", None, None)
        count += 1
    return count


def _bump(agg: dict[str, dict], raw: str, source: str, n: int) -> None:
    key = norm(raw)
    entry = agg.setdefault(key, {"raw": raw, "sources": set(), "count": 0})
    entry["sources"].add(source)
    entry["count"] += n
