"""Name-resolution service: link raw client / employee names to master records.

Tally and the timesheet spell the same client differently ("XYZ Corporate" vs
"XYZ Corporate Pvt Ltd"); the timesheet and salary sheet spell employees
differently too. The operator confirms a match once and it is remembered as an
alias, so future imports resolve automatically.
"""

from __future__ import annotations

import re

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

    Applies to ALL voucher kinds (sales + expenses). Most expense vouchers
    have a vendor as their party and won't match anything in the client
    master — those just stay unmapped. But when an expense voucher's party
    *does* happen to be in the client master (e.g. a journal/credit-note
    raised against a client, a reimbursement-from-client recorded as a
    receipt-type voucher), the link gets populated so the Client column
    on the Expenses sheet shows the real name.
    """
    linked = 0
    rows = conn.execute(
        "SELECT id, party_name FROM vouchers "
        "WHERE client_id IS NULL AND party_name <> ''").fetchall()
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
    """Return the most likely cost-centre id for a raw party name.

    Strategy (each step falls through to the next if it produces nothing):

    1. **Resolved splits**: the dominant ``cost_centre_id`` already on
       sales-voucher splits matching this party name. Most reliable —
       it's the consensus of whatever auto-match has previously decided.
    2. **Raw CC strings on splits**: take the most-common
       ``raw_cost_centre`` text from those same vouchers' splits and
       fuzzy-match it against the partner master (low threshold, since
       this fills the resolve dialog where the operator will confirm).
       Handles the case where every split is still unmapped — common on
       a fresh Tally pull before the operator has clicked through any
       review entries.

    Used to pre-fill the resolve-client dialog so the operator doesn't
    have to manually pick the partner that Tally already told us about.
    """
    if not raw:
        return None
    key = norm(raw)
    with transaction() as conn:
        rows = conn.execute(
            "SELECT v.id, v.party_name "
            "FROM vouchers v WHERE v.kind = 'sales' "
            "AND v.party_name <> ''").fetchall()
        ids = [r["id"] for r in rows if norm(r["party_name"]) == key]
        if not ids:
            return None
        ph = ",".join("?" * len(ids))
        # Step 1: resolved cost_centre_id consensus.
        row = conn.execute(
            f"SELECT s.cost_centre_id, COUNT(*) AS n "
            f"FROM voucher_splits s "
            f"WHERE s.voucher_id IN ({ph}) "
            f"AND s.cost_centre_id IS NOT NULL "
            f"GROUP BY s.cost_centre_id ORDER BY n DESC LIMIT 1",
            ids).fetchone()
        if row:
            return row["cost_centre_id"]
        # Step 2: fall back to the dominant raw_cost_centre text.
        raw_row = conn.execute(
            f"SELECT s.raw_cost_centre AS raw, COUNT(*) AS n "
            f"FROM voucher_splits s "
            f"WHERE s.voucher_id IN ({ph}) "
            f"AND s.raw_cost_centre IS NOT NULL "
            f"AND s.raw_cost_centre <> '' "
            f"GROUP BY s.raw_cost_centre ORDER BY n DESC LIMIT 1",
            ids).fetchone()
    if raw_row:
        cc_id, _mgr_id, _score = suggest_for_raw_cc(raw_row["raw"])
        return cc_id
    return None


# --- "delete unmapped rows" helpers used by the Review page ---------------

def delete_unmapped_client_rows(raw: str) -> int:
    """Permanently delete every sales voucher + timesheet line whose raw
    name matches *raw* (whitespace-insensitive). Use when an unmapped client
    name is bogus / shouldn't be in the MIS at all.

    Returns the number of source rows deleted.
    """
    key = norm(raw)
    deleted = 0
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, party_name FROM vouchers "
            "WHERE kind = 'sales' AND client_id IS NULL "
            "AND party_name <> ''").fetchall()
        v_ids = [r["id"] for r in rows if norm(r["party_name"]) == key]
        if v_ids:
            ph = ",".join("?" * len(v_ids))
            conn.execute(f"DELETE FROM vouchers WHERE id IN ({ph})", v_ids)
            deleted += len(v_ids)
        rows = conn.execute(
            "SELECT id, client_raw FROM timesheet_entries "
            "WHERE client_id IS NULL AND client_raw <> ''").fetchall()
        t_ids = [r["id"] for r in rows if norm(r["client_raw"]) == key]
        if t_ids:
            ph = ",".join("?" * len(t_ids))
            conn.execute(
                f"DELETE FROM timesheet_entries WHERE id IN ({ph})", t_ids)
            deleted += len(t_ids)
    return deleted


def delete_unmapped_employee_rows(raw: str) -> int:
    """Permanently delete every timesheet + salary row for an employee name
    (whitespace-insensitive). Returns the number of source rows deleted."""
    key = norm(raw)
    deleted = 0
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, emp_name FROM timesheet_entries "
            "WHERE emp_name <> ''").fetchall()
        ts_ids = [r["id"] for r in rows if norm(r["emp_name"]) == key]
        if ts_ids:
            ph = ",".join("?" * len(ts_ids))
            conn.execute(
                f"DELETE FROM timesheet_entries WHERE id IN ({ph})", ts_ids)
            deleted += len(ts_ids)
        rows = conn.execute(
            "SELECT id, employee_name FROM salary_entries "
            "WHERE employee_name <> ''").fetchall()
        s_ids = [r["id"] for r in rows if norm(r["employee_name"]) == key]
        if s_ids:
            ph = ",".join("?" * len(s_ids))
            conn.execute(
                f"DELETE FROM salary_entries WHERE id IN ({ph})", s_ids)
            deleted += len(s_ids)
    return deleted


def delete_unmapped_cc_string_rows(raw: str) -> int:
    """Permanently delete every voucher split whose raw Cost-Centre string
    matches *raw* (whitespace-insensitive). A voucher is removed entirely
    only when all of its splits get deleted (FK cascade on the splits).

    Uses each split's own ``raw_cost_centre`` (falling back to the parent
    voucher's for legacy data), so a multi-CC voucher only loses the splits
    tagged with the offending string — the rest of the voucher stays.
    """
    key = norm(raw)
    deleted = 0
    with transaction() as conn:
        rows = conn.execute(
            "SELECT s.id, "
            "       coalesce(s.raw_cost_centre, v.raw_cost_centre) AS raw "
            "FROM voucher_splits s "
            "JOIN vouchers v ON v.id = s.voucher_id "
            "WHERE coalesce(s.raw_cost_centre, v.raw_cost_centre) <> ''"
        ).fetchall()
        s_ids = [r["id"] for r in rows if norm(r["raw"]) == key]
        if s_ids:
            ph = ",".join("?" * len(s_ids))
            conn.execute(
                f"DELETE FROM voucher_splits WHERE id IN ({ph})", s_ids)
            deleted += len(s_ids)
            # Clean up any vouchers that lost their last split.
            conn.execute(
                "DELETE FROM vouchers WHERE id NOT IN "
                "  (SELECT DISTINCT voucher_id FROM voucher_splits)")
    return deleted


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
    voucher_split whose own ``raw_cost_centre`` matches the saved string.

    The voucher-dump parser tags each split with its line-level cost-centre
    string (different services on the same voucher can go to different
    partners), so we resolve at split level — not at voucher level.

    Falls back to the parent voucher's ``raw_cost_centre`` for legacy splits
    that don't have their own string yet (pre-v5 schema rows).

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
        # Per-split mapping — splits with their own raw_cost_centre.
        splits = conn.execute(
            "SELECT s.id, "
            "       coalesce(s.raw_cost_centre, v.raw_cost_centre) AS cc "
            "FROM voucher_splits s "
            "JOIN vouchers v ON v.id = s.voucher_id "
            "WHERE s.cost_centre_id IS NULL "
            "  AND coalesce(s.raw_cost_centre, v.raw_cost_centre) <> ''"
        ).fetchall()
        buckets: dict[str, list[int]] = {}
        for s in splits:
            n = norm(s["cc"])
            if n in mappings:
                buckets.setdefault(n, []).append(s["id"])
        for n, ids in buckets.items():
            cc_id, mgr_id = mappings[n]
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"UPDATE voucher_splits SET cost_centre_id = ?, manager_id = ? "
                f"WHERE id IN ({placeholders})",
                (cc_id, mgr_id, *ids))
            updated += cur.rowcount
    return updated


def unresolved_cc_strings() -> list[dict]:
    """Distinct ``raw_cost_centre`` strings (from voucher splits) that have
    no saved mapping yet. Whitespace-insensitive.

    Pulled from ``voucher_splits.raw_cost_centre`` first (per-line CC from
    the voucher-dump parser), falling back to ``vouchers.raw_cost_centre``
    when the split doesn't carry its own string (legacy data).
    """
    with transaction() as conn:
        known = {norm(r["raw_text"]) for r in conn.execute(
            "SELECT raw_text FROM cc_string_mappings WHERE active = 1")}
        rows = conn.execute(
            "SELECT coalesce(s.raw_cost_centre, v.raw_cost_centre) AS raw "
            "FROM voucher_splits s "
            "JOIN vouchers v ON v.id = s.voucher_id "
            "WHERE s.cost_centre_id IS NULL "
            "  AND coalesce(s.raw_cost_centre, v.raw_cost_centre) <> ''"
        ).fetchall()
    agg: dict[str, dict] = {}
    for r in rows:
        n = norm(r["raw"])
        if n in known:
            continue
        entry = agg.setdefault(n, {"raw": r["raw"], "count": 0})
        entry["count"] += 1
    return sorted(agg.values(), key=lambda d: -d["count"])


# --- Smart auto-match for Cost-Centre strings -------------------------------

_HONORIFICS = re.compile(
    r'^(mr|mrs|ms|dr|shri|smt|sri)\.?\s*', re.IGNORECASE)
_NAME_SEP = re.compile(r'\s*[-–—/,&]\s*')

# Token boundaries for query splitting in _best_match. Far broader than
# whitespace — real Tally CC strings often use underscores, dots, parens
# etc as separators ("VK_Audit", "VK.2026", "VK(Audit)"). We also split
# at alpha/digit boundaries so "VK2026" → "vk" + "2026".
_TOKEN_SEP = re.compile(r'[\s\-–—/,;:|.()\[\]_&]+')
_ALPHANUM_BOUNDARY = re.compile(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])')


def _tokenize(query: str) -> set[str]:
    """Aggressively tokenize a query for token-level exact match.

    Splits on whitespace + every common separator character (``_``,
    ``.``, ``,``, ``;``, ``:``, ``|``, ``()``, ``[]``, ``&`` etc.) and
    then breaks alpha/digit transitions so ``VK2026`` becomes
    ``{vk, 2026}``. Used by ``_best_match`` to recover partner names
    that are embedded in operator-customised CC strings.
    """
    parts = _TOKEN_SEP.split(query)
    out: set[str] = set()
    for part in parts:
        if not part:
            continue
        # Split alpha-to-digit boundaries: "VK2026" -> ["vk", "2026"]
        sub = _ALPHANUM_BOUNDARY.split(part)
        for s in sub:
            if s:
                out.add(s)
    return out
# Fuzzy threshold for the auto-apply path. Partners are a fixed set of 8
# masters so we can be more lenient than for clients/employees. 65 lands
# in a sweet spot now that we have unambiguous-singleton lookups + tie
# detection — most real-world CC strings ("VK Audit 2026", "Mr Vishal K",
# "Vishal-Recovery") match a partner at 75+; the unambiguous-singleton
# logic prevents short-string fuzzy false positives, so 65 doesn't open
# us up to wrong matches in practice.
_MIN_SCORE = 65


def _best_match(query: str, lookup: dict[str, int]) -> tuple[int | None, int]:
    """Best (id, score) for *query* in {normalised_name: id}.

    Strategy:

    1. **Exact full-query**: ``query in lookup`` → score 100.
    2. **Token-level exact**: each whitespace-separated token of the
       query is checked against the lookup. If exactly one master id
       comes back across all matching tokens, that's the answer.
       Catches "VK Audit 2026" → VK ("vk" token matches), "Vishal
       Audit" → VK ("vishal" matches), "PM Tax" → PM, etc., without
       relying on lenient partial-ratio scoring.
    3. **Fuzzy fallback**, restricted to keys of length ≥ 4. Short
       codes ("vk", "pm", "al", "ks", …) stay in the exact lookup
       (passes 1 + 2) but are excluded here so they can't generate
       partial-ratio false positives against unrelated text ("audit"
       contains "al"; "random" contains "ran" matching "kiran"). For
       partial_ratio we require a high bar (85+) — token_sort runs
       full-range. Tie detection still applies: multiple keys mapping
       to *different* ids at the top score → refuse to guess.
    """
    if not query or not lookup:
        return None, 0
    # 1. Exact whole-query match
    if query in lookup:
        return lookup[query], 100
    # 2. Token-level exact match. Uses a broad tokenizer (splits on
    # whitespace + underscores + dots + parens + slashes + commas, plus
    # alpha/digit boundaries) so partner identifiers buried inside
    # operator-customised strings still surface: "VK_Audit",
    # "VK.2026", "VK(Audit)", "VK2026Q1" all yield the "vk" token.
    tokens = _tokenize(query)
    if tokens:
        token_ids = {lookup[t] for t in tokens if t in lookup}
        if len(token_ids) == 1:
            return next(iter(token_ids)), 100
        if len(token_ids) > 1:
            # Ambiguous tokens (e.g. multiple partner singletons in one
            # query) — better to leave it for the operator to choose.
            return None, 0
    # 3. Fuzzy fallback on long-enough keys
    fuzzy_keys = {k for k in lookup if len(k) >= 4}
    if not fuzzy_keys:
        return None, 0
    best_per_key: dict[str, float] = {}
    for key, score, _ in process.extract(
            query, fuzzy_keys, scorer=fuzz.token_sort_ratio, limit=5):
        if score > best_per_key.get(key, 0):
            best_per_key[key] = score
    for key, score, _ in process.extract(
            query, fuzzy_keys, scorer=fuzz.partial_ratio, limit=5):
        # Partial-ratio is overly forgiving on short queries against
        # short substrings — require a much higher bar.
        if score >= 85 and score > best_per_key.get(key, 0):
            best_per_key[key] = score
    if not best_per_key:
        return None, 0
    top_score = max(best_per_key.values())
    top_ids = {lookup[k] for k, s in best_per_key.items()
               if s == top_score}
    if len(top_ids) > 1:
        return None, 0
    top_key = next(k for k, s in best_per_key.items() if s == top_score)
    return lookup[top_key], int(top_score)


def _build_partner_manager_lookups(conn) -> tuple[dict, dict]:
    """Build the {normalised name → id} lookups for partners and managers.

    Each lookup includes:

    * the full canonical name (always)
    * the code (always)
    * **unambiguous** name-part singletons (length ≥ 4, appearing in
      exactly one entry). So "Vishal", "Kothari" → VK; "Shreyans",
      "Dedhia" → SD; but "Mehta" (shared across PM / AM / MS) is
      deliberately excluded — we can't pick one without context.
    """
    return (_build_lookup(conn,
                           "SELECT id, code, name FROM cost_centres "
                           "WHERE active = 1 AND cc_type = 'partner'"),
            _build_lookup(conn,
                           "SELECT id, code, name FROM managers "
                           "WHERE active = 1"))


def _build_lookup(conn, sql: str) -> dict[str, int]:
    """Helper: build the lookup dict for one master table."""
    rows = list(conn.execute(sql))
    lookup: dict[str, int] = {}
    # First pass: count which name-parts belong to which ids.
    part_owners: dict[str, set] = {}
    for r in rows:
        for part in norm(r["name"]).split():
            if len(part) >= 4:
                part_owners.setdefault(part, set()).add(r["id"])
    # Second pass: build the lookup with full names + codes + unambiguous parts.
    for r in rows:
        lookup[norm(r["name"])] = r["id"]
        lookup[norm(r["code"])] = r["id"]
        for part in norm(r["name"]).split():
            if len(part) >= 4 and len(part_owners.get(part, ())) == 1:
                lookup.setdefault(part, r["id"])
    return lookup


def _match_one_cc_string(raw: str, partner_lookup: dict, manager_lookup: dict,
                          min_score: int = _MIN_SCORE
                          ) -> tuple[int | None, int | None, int]:
    """Match a single CC string. Returns ``(cc_id, mgr_id, score)``.

    Same logic as :func:`auto_match_cc_strings` distilled to one string.
    *min_score* controls how confident we need to be — 70 is the auto-
    apply threshold; 50 is what the SplitEditor uses for *suggestions*
    where the operator will confirm before saving.
    """
    cleaned = norm(_HONORIFICS.sub("", (raw or "").strip()))
    if not cleaned:
        return None, None, 0
    cc_id: int | None = None
    mgr_id: int | None = None
    best_score = 0

    # "X - Y" — try both as the partner side.
    parts = _NAME_SEP.split(cleaned, maxsplit=1)
    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        l_id, l_score = _best_match(left, partner_lookup)
        r_id, r_score = _best_match(right, partner_lookup)
        if r_score >= l_score and r_score >= min_score:
            cc_id, best_score = r_id, r_score
            m_id, m_score = _best_match(left, manager_lookup)
            if m_score >= min_score:
                mgr_id = m_id
        elif l_score >= min_score:
            cc_id, best_score = l_id, l_score
            m_id, m_score = _best_match(right, manager_lookup)
            if m_score >= min_score:
                mgr_id = m_id
    # Plain — try the whole string as a partner.
    if cc_id is None:
        id_w, score_w = _best_match(cleaned, partner_lookup)
        if score_w >= min_score:
            cc_id, best_score = id_w, score_w
    return cc_id, mgr_id, best_score


def export_cc_diagnostic(path: str) -> int:
    """Write a CSV with FULL visibility into the state of every voucher
    split's cost-centre attribution. Returns the row count written.

    Includes three kinds of rows so the operator (and we) can see the
    full picture:

    * **Summary** row at the top: total splits, how many are resolved,
      how many have raw text but aren't resolved, how many have no
      raw text at all (the "Tally didn't tag a CC" case).
    * **Unresolved with raw text** rows: the standard matcher diagnosis.
    * **Unresolved with NO raw text** rows (limited sample): voucher
      number, party, ledger — so the operator can verify whether the
      Tally XML actually has CC tags on those specific vouchers.

    If most rows fall into the third category, the issue is XML
    extraction (share ``tally_last_response.xml``); if most are in
    category 2 with a "suggested partner", it's a matcher gap.
    """
    import csv
    with transaction() as conn:
        partner_codes = {
            r["id"]: r["code"] for r in conn.execute(
                "SELECT id, code FROM cost_centres "
                "WHERE active = 1 AND cc_type = 'partner'")}
        partner_lookup, manager_lookup = _build_partner_manager_lookups(conn)
        saved = {norm(r["raw_text"]): r["cost_centre_id"]
                  for r in conn.execute(
                      "SELECT raw_text, cost_centre_id FROM "
                      "cc_string_mappings WHERE active = 1")}
        # Get full counts up front.
        totals = conn.execute("""
            SELECT
              COUNT(*) AS total_splits,
              SUM(CASE WHEN s.cost_centre_id IS NOT NULL THEN 1 ELSE 0 END) AS resolved,
              SUM(CASE WHEN s.cost_centre_id IS NULL
                       AND coalesce(s.raw_cost_centre, v.raw_cost_centre, '') <> ''
                       THEN 1 ELSE 0 END) AS unresolved_with_raw,
              SUM(CASE WHEN s.cost_centre_id IS NULL
                       AND coalesce(s.raw_cost_centre, v.raw_cost_centre, '') = ''
                       THEN 1 ELSE 0 END) AS unresolved_no_raw
            FROM voucher_splits s
            JOIN vouchers v ON v.id = s.voucher_id
        """).fetchone()
        # Sample of "no raw CC at all" splits — the smoking gun for an
        # XML-extraction problem.
        no_raw_samples = conn.execute("""
            SELECT v.vch_no, v.vch_type, v.party_name, v.kind,
                   v.ledger_head, v.txn_date
            FROM voucher_splits s
            JOIN vouchers v ON v.id = s.voucher_id
            WHERE s.cost_centre_id IS NULL
              AND coalesce(s.raw_cost_centre, v.raw_cost_centre, '') = ''
            ORDER BY v.txn_date DESC
            LIMIT 20
        """).fetchall()

    rows = unresolved_cc_strings()
    written = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Summary header.
        w.writerow([
            "=== SUMMARY ===", "", "", "", "", "", "", "",
        ])
        w.writerow([
            "Total splits",
            "Resolved (have cost_centre_id)",
            "Unresolved WITH raw CC string",
            "Unresolved WITHOUT raw CC string (XML extraction issue!)",
            "", "", "", "",
        ])
        w.writerow([
            totals["total_splits"] or 0,
            totals["resolved"] or 0,
            totals["unresolved_with_raw"] or 0,
            totals["unresolved_no_raw"] or 0,
            "", "", "", "",
        ])
        w.writerow([])
        # Matcher diagnosis for unresolved-with-raw rows.
        w.writerow([
            "=== UNRESOLVED CC STRINGS (matcher diagnosis) ===",
            "", "", "", "", "", "", "",
        ])
        w.writerow([
            "raw_text", "normalised", "tokens",
            "saved_mapping_partner", "suggested_partner", "score",
            "splits_affected", "diagnosis",
        ])
        for r in rows:
            raw = r["raw"]
            cleaned = norm(_HONORIFICS.sub("", (raw or "").strip()))
            tokens = sorted(_tokenize(cleaned))
            cc_id, mgr_id, score = _match_one_cc_string(
                raw, partner_lookup, manager_lookup, min_score=50)
            saved_cc_id = saved.get(norm(raw))
            saved_partner = partner_codes.get(saved_cc_id)
            suggested_partner = partner_codes.get(cc_id)
            if saved_partner:
                diag = ("HAS MAPPING but split unresolved — apply path "
                        "didn't fire (BUG, share this row)")
            elif suggested_partner and score >= _MIN_SCORE:
                diag = ("matcher would resolve at %d%% — auto-match "
                        "should fire on next pull (try Auto-match all)"
                        % score)
            elif suggested_partner:
                diag = ("low confidence %d%% — use Confirm suggested or "
                        "resolve manually" % score)
            else:
                diag = ("no plausible partner — operator must pick "
                        "manually OR this isn't a partner CC")
            w.writerow([
                raw, cleaned, "|".join(tokens),
                saved_partner or "", suggested_partner or "",
                score, r["count"], diag,
            ])
            written += 1
        w.writerow([])
        # Sample of "no CC at all" vouchers — extraction-issue evidence.
        w.writerow([
            "=== UNRESOLVED VOUCHERS WITH NO RAW CC AT ALL "
            "(XML extraction issue - sample of 20) ===",
            "", "", "", "", "", "", "",
        ])
        w.writerow([
            "vch_no", "vch_type", "party_name", "kind", "ledger_head",
            "txn_date", "", "",
        ])
        for s in no_raw_samples:
            w.writerow([
                s["vch_no"] or "", s["vch_type"] or "",
                s["party_name"] or "", s["kind"] or "",
                s["ledger_head"] or "", s["txn_date"] or "",
                "", "",
            ])
    return written


def diagnose_unresolved_cc(limit: int = 10) -> list[dict]:
    """Return diagnostic rows for unresolved CC strings.

    For each distinct unresolved string, returns ``{"raw", "count",
    "suggested_partner", "score"}`` so the operator can see:

    * which strings are NOT being auto-resolved
    * how many splits each string blocks
    * what the matcher *would* suggest at suggest-threshold 50 (low
      bar to catch near-matches the auto-apply path skipped)

    If a suggestion has score ≥ 65 (the auto-apply threshold) but the
    string still appears unresolved, something is wrong on the apply
    path — the diagnostic surfaces this gap directly so we can debug.
    """
    rows = unresolved_cc_strings()
    out = []
    with transaction() as conn:
        partner_codes = {
            r["id"]: r["code"] for r in conn.execute(
                "SELECT id, code FROM cost_centres "
                "WHERE active = 1 AND cc_type = 'partner'")}
    for r in rows[:limit]:
        raw = r["raw"]
        cc_id, mgr_id, score = suggest_for_raw_cc(raw, min_score=50)
        out.append({
            "raw": raw,
            "count": r["count"],
            "suggested_partner": partner_codes.get(cc_id),
            "suggested_partner_id": cc_id,
            "suggested_manager_id": mgr_id,
            "score": score,
        })
    return out


def suggest_for_raw_cc(raw: str, min_score: int = 80
                        ) -> tuple[int | None, int | None, int]:
    """Suggest a (partner CC id, manager id, confidence score) for a raw
    Tally CC string. Designed for UI pre-filling.

    Threshold defaults to 80 — higher than the auto-match's 70 — because
    weak partial-ratio matches against short singleton keys (e.g.
    "random" loosely overlapping "kiran") can score in the 70s and
    pre-fill the wrong partner. 80+ keeps suggestions reliable; the
    operator can always pick manually when no suggestion is shown.

    Looks up the saved ``cc_string_mappings`` table first; if there's
    no saved mapping it falls back to fuzzy matching with the supplied
    threshold.
    """
    if not raw or not raw.strip():
        return None, None, 0
    with transaction() as conn:
        # Saved mapping has priority — it's the operator's own decision.
        row = conn.execute(
            "SELECT cost_centre_id, manager_id FROM cc_string_mappings "
            "WHERE lower(trim(raw_text)) = ? AND active = 1",
            (raw.strip().lower(),)).fetchone()
        if row:
            return row["cost_centre_id"], row["manager_id"], 100
        partner_lookup, manager_lookup = _build_partner_manager_lookups(conn)
    return _match_one_cc_string(
        raw, partner_lookup, manager_lookup, min_score)


def auto_match_cc_strings() -> int:
    """For every still-unmapped Cost-Centre string, fuzzy-match it to a
    partner (and optionally a manager) and create the mapping automatically.

    Handles patterns like:
      • "Mr. Shreyans Dedhia"  → SD (strip honorific, exact match)
      • "Megha Mehta"          → MS (direct match)
      • "Prashant - Shreyans"  → SD, manager "Prashant" if known
      • "Gaurav S - Aakash"    → AM, manager GS (fuzzy on both sides)
      • "Jalpesh - Umesh"      → JV, manager UV (tries both orderings,
                                  picks whichever yields a partner)

    Returns the number of new mappings created. Existing mappings are
    overwritten only if the auto-match finds a better fit.
    """
    with transaction() as conn:
        partner_lookup, manager_lookup = _build_partner_manager_lookups(conn)

    if not partner_lookup:
        return 0

    new_mappings: list[tuple[str, int, int | None]] = []
    for item in unresolved_cc_strings():
        raw = item["raw"]
        cc_id, mgr_id, _score = _match_one_cc_string(
            raw, partner_lookup, manager_lookup, _MIN_SCORE)
        if cc_id is not None:
            new_mappings.append((raw, cc_id, mgr_id))

    if not new_mappings:
        return 0

    with transaction() as conn:
        for raw, cc_id, mgr_id in new_mappings:
            conn.execute(
                "INSERT INTO cc_string_mappings "
                "(raw_text, cost_centre_id, manager_id) VALUES (?, ?, ?) "
                "ON CONFLICT(raw_text) DO UPDATE SET "
                "  cost_centre_id = excluded.cost_centre_id, "
                "  manager_id = excluded.manager_id, "
                "  active = 1",
                (raw, cc_id, mgr_id))
    # Apply the new mappings to existing voucher splits.
    apply_known_cc_string_mappings()
    infer_all_masters()
    return len(new_mappings)


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
