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
    # Reimbursements: same logic — link client_raw to the master.
    rows = conn.execute(
        "SELECT id, client_raw FROM reimbursements "
        "WHERE client_id IS NULL AND client_raw <> ''").fetchall()
    for r in rows:
        cid = name_to_cid.get(norm(r["client_raw"]))
        if cid is not None:
            conn.execute(
                "UPDATE reimbursements SET client_id = ? WHERE id = ?",
                (cid, r["id"]))
            linked += 1
    return linked


def match_entity(raw_name: str, *,
                  letterhead_text: str | None = None,
                  fuzzy_threshold: int = 70
                  ) -> int | None:
    """Resolve a raw entity name (+ optional letterhead) to an entity id.

    Checks (in order):

    1. **Letterhead alias scan** (when ``letterhead_text`` is given).
       Walks every active entity's name + aliases looking for matches
       inside the full letterhead text (lowercased substring). Picks
       the entity with the longest distinctive match. This is what
       lets us tell Bilimoria Mumbai (no "Bengaluru" in letterhead)
       from Bilimoria Bangalore (has "Bengaluru" in letterhead) when
       both share the company name "Bilimoria Mehta & Co.".
    2. Exact normalised match against ``entities.name``.
    3. Exact match against ``entity_aliases.alias``.
    4. Fuzzy match (``token_sort_ratio``) against active entity names,
       requiring at least ``fuzzy_threshold`` AND a 5-point gap to the
       runner-up. Below that bar we return ``None`` — the operator
       picks the entity manually.

    Used by the Import page to auto-populate the entity dropdown from
    the letterhead of a Tally export.
    """
    if not raw_name and not letterhead_text:
        return None

    with transaction() as conn:
        # Step 1: letterhead alias scan.
        #
        # Aliases are the disambiguating signal — they're seeded
        # explicitly to tell sibling entities apart (e.g. "Bengaluru"
        # only belongs to the Bangalore branch). When two entities share
        # a company name (Bilimoria Mumbai and Bangalore both call
        # themselves "Bilimoria Mehta & Co."), a NAME match is ambiguous;
        # an ALIAS match is decisive.
        #
        # Scoring per entity = (alias_hit_count, longest_alias_hit_length).
        # Most alias hits wins; ties broken by longest individual alias.
        # Name matches are tried only after the alias pass, and only
        # when no aliases hit anywhere.
        if letterhead_text:
            low_letter = letterhead_text.lower()
            alias_scored: dict[int, list[int]] = {}  # eid -> list of hit lengths
            for r in conn.execute(
                    "SELECT a.entity_id, a.alias FROM entity_aliases a "
                    "JOIN entities e ON e.id = a.entity_id "
                    "WHERE e.active = 1"):
                low_alias = r["alias"].lower()
                if low_alias in low_letter:
                    alias_scored.setdefault(
                        r["entity_id"], []).append(len(low_alias))
            if alias_scored:
                ranked = sorted(
                    alias_scored.items(),
                    key=lambda kv: (len(kv[1]), max(kv[1])),
                    reverse=True)
                top_eid, top_hits = ranked[0]
                if len(ranked) == 1:
                    return top_eid
                _, runner_hits = ranked[1]
                top_key = (len(top_hits), max(top_hits))
                runner_key = (len(runner_hits), max(runner_hits))
                if top_key > runner_key:
                    return top_eid
                # Otherwise fall through — tie among alias-matching
                # entities, let the next steps disambiguate.

            # Fallback: longest entity NAME found in the letterhead.
            # Skipped when aliases tied so we don't override with the
            # ambiguous-name signal we already rejected.
            if not alias_scored:
                name_scored: dict[int, int] = {}
                for r in conn.execute(
                        "SELECT id, name FROM entities WHERE active = 1"):
                    low_name = r["name"].lower()
                    if low_name in low_letter:
                        prev = name_scored.get(r["id"], 0)
                        if len(low_name) > prev:
                            name_scored[r["id"]] = len(low_name)
                if name_scored:
                    ranked = sorted(name_scored.items(),
                                     key=lambda kv: kv[1], reverse=True)
                    if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
                        return ranked[0][0]

        if not raw_name:
            return None
        key = norm(raw_name)
        if not key:
            return None
        # Step 2: exact name.
        row = conn.execute(
            "SELECT id FROM entities WHERE lower(trim(name)) = ?",
            (key,)).fetchone()
        if row:
            return row["id"]
        # Step 3: exact alias.
        row = conn.execute(
            "SELECT entity_id FROM entity_aliases "
            "WHERE lower(trim(alias)) = ?",
            (key,)).fetchone()
        if row:
            return row["entity_id"]
        # Step 4: fuzzy on names.
        entities = [(r["id"], r["name"]) for r in conn.execute(
            "SELECT id, name FROM entities WHERE active = 1")]
    if not entities:
        return None
    target = norm_loose(raw_name)
    norms = {eid: norm_loose(name) for eid, name in entities}
    ranked = process.extract(
        target, norms, scorer=fuzz.token_sort_ratio, limit=3)
    if not ranked:
        return None
    top_score = int(ranked[0][1])
    top_id = ranked[0][2]
    runner = int(ranked[1][1]) if len(ranked) > 1 else 0
    if top_score >= fuzzy_threshold and (top_score - runner) >= 5:
        return top_id
    return None


def apply_known_client_aliases(*, fuzzy_threshold: int = 70,
                                 skip_fuzzy: bool = False) -> int:
    """Auto-link unresolved rows whose raw name matches a known client/alias.

    Two passes:

    1. **Exact**: normalised raw name == normalised canonical / alias.
    2. **Fuzzy** (at ``fuzzy_threshold`` and above, default 70): catches
       harmless variants like ``PROCAM INTERNATIONAL PVT. LTD`` →
       ``Procam International Private Limited`` that ``norm()``'s
       whitespace+case folding misses. Only auto-applies when the top
       fuzzy candidate is clearly ahead of the runner-up (≥5pt gap);
       otherwise the row is left for the operator's review queue.
       Successful fuzzy links are saved as aliases so re-imports hit
       the cheap exact path.

    Also infers client → cost-centre links from the freshly-linked vouchers.
    """
    with transaction() as conn:
        pairs: dict[str, int] = {}
        # Aliases first so canonical names OVERWRITE them on key collision.
        # Without this, a stale alias (often left over from a previous
        # mis-click in the Review dialog or an old fuzzy guess) would
        # silently override a correct canonical-name match — the
        # operator's authoritative master row would never get a chance
        # to win.
        for r in conn.execute(
                "SELECT client_id, alias_text FROM client_aliases"):
            pairs[norm(r["alias_text"])] = r["client_id"]
        for r in conn.execute("SELECT id, canonical_name FROM clients"):
            pairs[norm(r["canonical_name"])] = r["id"]
        linked = _apply_client_norm_mapping(conn, pairs)
    if not skip_fuzzy:
        linked += _fuzzy_link_clients(threshold=fuzzy_threshold)
    infer_all_masters()
    return linked


def _fuzzy_link_clients(*, threshold: int = 70, gap: int = 5) -> int:
    """Fuzzy-match each still-unresolved party / client_raw to a client.

    For each unmatched raw name, ranks active clients by token_sort_ratio.
    Auto-link when:

    * top score is at or above ``threshold`` (default 70), AND
    * top score is at least ``gap`` points ahead of the runner-up.

    The gap requirement prevents tie-misfires when several similar clients
    exist (e.g. ``Procam International Pvt Ltd Delhi`` vs ``Procam Kolkata``).

    Each linked raw name is saved as an alias on the client so subsequent
    imports of the same wording hit the exact-match fast path.
    """
    linked = 0
    with transaction() as conn:
        clients = [
            (r["id"], r["canonical_name"]) for r in conn.execute(
                "SELECT id, canonical_name FROM clients WHERE active = 1")]
        if not clients:
            return 0
        norms = {cid: norm_loose(name) for cid, name in clients}

        # Gather every still-unresolved raw name (vouchers + timesheet).
        raws: set[str] = set()
        for r in conn.execute(
                "SELECT DISTINCT party_name FROM vouchers "
                "WHERE client_id IS NULL AND party_name <> ''"):
            raws.add(r["party_name"])
        for r in conn.execute(
                "SELECT DISTINCT client_raw FROM timesheet_entries "
                "WHERE client_id IS NULL AND client_raw <> ''"):
            raws.add(r["client_raw"])
        if not raws:
            return 0

        # Score each raw name; auto-link the clear-winner cases.
        confident: dict[str, int] = {}
        for raw in raws:
            target = norm_loose(raw)
            if not target:
                continue
            ranked = process.extract(
                target, norms, scorer=fuzz.token_sort_ratio, limit=3)
            if not ranked:
                continue
            top_score = int(ranked[0][1])
            top_id = ranked[0][2]
            runner = int(ranked[1][1]) if len(ranked) > 1 else 0
            if top_score >= threshold and (top_score - runner) >= gap:
                confident[norm(raw)] = top_id
                # Remember the raw text as an alias so re-imports skip
                # the fuzzy pass entirely.
                conn.execute(
                    "INSERT OR IGNORE INTO client_aliases "
                    "(client_id, alias_text, source) VALUES (?, ?, 'fuzzy')",
                    (top_id, raw))
        if confident:
            linked = _apply_client_norm_mapping(conn, confident)
    return linked


def unresolved_clients() -> list[dict]:
    """Distinct raw party names not yet linked, with their source counts.

    Pulls from EVERY table that carries a client-link column —
    sales vouchers, purchase vouchers, timesheet entries, and the
    per-row reimbursement sheet. Pre-v0.3.66 only sales + timesheet
    were queried, so purchase-register parties (e.g. a vendor name
    that turns out to actually be a billable client whose master
    row doesn't exist yet) silently never surfaced in the Review
    queue. Same omission for reimbursement client_raw values.

    Most purchase-register parties ARE vendors and won't be mapped —
    that's fine, they just stay unmapped. But the few that are
    legitimately clients (or recharged-to-client expenses the firm
    tracks per partner) now show up so the operator can map them.
    Sort order is by count descending so the high-volume entries
    bubble to the top regardless of which table they came from.
    """
    with transaction() as conn:
        agg: dict[str, dict] = {}
        for r in conn.execute(
                "SELECT party_name AS raw, COUNT(*) AS n FROM vouchers "
                "WHERE kind = 'sales' AND client_id IS NULL "
                "AND party_name <> '' GROUP BY lower(trim(party_name))"):
            _bump(agg, r["raw"], "Sales", r["n"])
        for r in conn.execute(
                "SELECT party_name AS raw, COUNT(*) AS n FROM vouchers "
                "WHERE kind = 'expense' AND client_id IS NULL "
                "AND party_name <> '' GROUP BY lower(trim(party_name))"):
            _bump(agg, r["raw"], "Purchase", r["n"])
        for r in conn.execute(
                "SELECT client_raw AS raw, COUNT(*) AS n FROM timesheet_entries "
                "WHERE client_id IS NULL AND client_raw <> '' "
                "GROUP BY lower(trim(client_raw))"):
            _bump(agg, r["raw"], "Timesheet", r["n"])
        for r in conn.execute(
                "SELECT client_raw AS raw, COUNT(*) AS n FROM reimbursements "
                "WHERE client_id IS NULL AND client_raw <> '' "
                "GROUP BY lower(trim(client_raw))"):
            _bump(agg, r["raw"], "Reimbursement", r["n"])
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
                   cost_centre_id: int | None,
                   manager_id: int | None = None) -> int:
    """Create a new client from a raw name and link all matching rows.

    Also REPOINTS any existing voucher / timesheet rows whose raw name
    matches the new canonical name but currently links to a different
    client — typical when the operator finally adds a master row to
    fix a stale fuzzy / Review-dialog mis-click.

    ``manager_id`` is accepted for back-compat with v0.3.47 callers
    but is no longer wired to the client master (DB column stays
    NULL for new rows).
    """
    if cost_centre_id is None:
        cost_centre_id = suggest_cc_for_raw_client(raw)
    with transaction() as conn:
        cid = conn.execute(
            "INSERT INTO clients (canonical_name, cost_centre_id) "
            "VALUES (?, ?)",
            (canonical_name, cost_centre_id)).lastrowid
        if norm(raw) != norm(canonical_name):
            conn.execute(
                "INSERT OR IGNORE INTO client_aliases (client_id, alias_text, source) "
                "VALUES (?, ?, 'tally')", (cid, raw))
        _link_client_rows(conn, raw, cid)
    # Outside the transaction since repoint_client_links opens its own.
    repoint_client_links(int(cid), canonical_name)
    return int(cid)


def _link_client_rows(conn, raw: str, client_id: int) -> int:
    """Set client_id on all rows whose raw name normalises to *raw*."""
    return _apply_client_norm_mapping(conn, {norm(raw): client_id})


def repoint_client_links(client_id: int, canonical_name: str) -> int:
    """Force every voucher / timesheet row whose raw name matches the
    given canonical (norm-equal) to point at ``client_id``.

    Unlike ``_apply_client_norm_mapping``, this OVERRIDES existing
    client_id values when they're wrong — the typical case being a
    stale fuzzy / accidental link to a different client that needs
    correcting now that the operator has added the right master row.

    Also wipes any ``client_aliases`` rows whose alias_text matches
    the canonical_name but points to a different client, so the
    next run of ``apply_known_client_aliases`` doesn't immediately
    undo this repoint.

    Returns the number of rows actually updated.
    """
    key = norm(canonical_name)
    if not key:
        return 0
    updated = 0
    with transaction() as conn:
        # 1. Drop conflicting aliases — same alias_text, different
        #    client_id. Keep aliases that already point to the right
        #    place (no-op).
        conn.execute(
            "DELETE FROM client_aliases "
            "WHERE lower(trim(alias_text)) = ? AND client_id <> ?",
            (key, client_id))
        # 2. Repoint vouchers + timesheet rows whose raw name matches
        #    AND currently point somewhere else (or nowhere).
        for table, raw_col in (
                ("vouchers", "party_name"),
                ("timesheet_entries", "client_raw"),
                ("reimbursements", "client_raw")):
            rows = conn.execute(
                f"SELECT id, {raw_col} FROM {table} "
                f"WHERE {raw_col} <> '' "
                f"  AND (client_id IS NULL OR client_id <> ?)",
                (client_id,)).fetchall()
            ids = [r["id"] for r in rows if norm(r[raw_col]) == key]
            if ids:
                ph = ",".join("?" * len(ids))
                cur = conn.execute(
                    f"UPDATE {table} SET client_id = ? "
                    f"WHERE id IN ({ph})", (client_id, *ids))
                updated += cur.rowcount
    return updated


def bulk_import_clients(
        pairs: list[tuple[str, str]],
        *,
        overwrite_existing_cc: bool = False
) -> dict:
    """Upsert clients from a list of ``(client_name, cc_code)`` pairs.

    For each row:

    * Look up the cost-centre by code (case-insensitive). Unknown codes
      go into the report's ``unknown_cc`` list and the client is skipped.
    * If a client with the same normalised canonical_name already exists:
      - leave cost_centre_id alone when it already points somewhere
        (unless ``overwrite_existing_cc=True``),
      - fill it in when it's NULL.
    * Otherwise insert a new client with that name + cost_centre_id.

    After the upsert, re-applies known aliases and infers downstream
    masters so any pre-existing vouchers linked to these clients pick up
    the new cost-centre via the v0.3.47 splits-fallback.

    Returns a dict with counts:
      ``created`` — new client rows inserted
      ``cc_set`` — existing clients whose NULL cost_centre_id was filled
      ``cc_overwritten`` — existing clients whose cost_centre_id changed
      ``unchanged`` — existing clients whose cost_centre already matched
      ``unknown_cc`` — list of (client, code) where the code wasn't a master
      ``rows_total`` — total rows processed
    """
    created = cc_set = cc_overwritten = unchanged = 0
    unknown_cc: list[tuple[str, str]] = []
    # Track newly-created clients so we can repoint stale links after
    # the transaction closes.
    newly_created: list[tuple[int, str]] = []
    with transaction() as conn:
        cc_by_code = {
            r["code"].strip().lower(): r["id"] for r in conn.execute(
                "SELECT id, code FROM cost_centres WHERE active = 1")}
        # Build a normalised-name → id index of existing clients once.
        existing: dict[str, tuple[int, int | None]] = {}
        for r in conn.execute(
                "SELECT id, canonical_name, cost_centre_id FROM clients"):
            existing[norm(r["canonical_name"])] = (r["id"], r["cost_centre_id"])
        for raw_name, raw_code in pairs:
            name = (raw_name or "").strip()
            code = (raw_code or "").strip()
            if not name:
                continue
            cc_id = cc_by_code.get(code.lower())
            if cc_id is None:
                unknown_cc.append((name, code))
                continue
            key = norm(name)
            hit = existing.get(key)
            if hit is None:
                # Insert new client.
                cid = conn.execute(
                    "INSERT INTO clients (canonical_name, cost_centre_id) "
                    "VALUES (?, ?)", (name, cc_id)).lastrowid
                existing[key] = (cid, cc_id)
                created += 1
                newly_created.append((int(cid), name))
            else:
                client_id, current_cc = hit
                if current_cc == cc_id:
                    unchanged += 1
                elif current_cc is None:
                    conn.execute(
                        "UPDATE clients SET cost_centre_id = ? WHERE id = ?",
                        (cc_id, client_id))
                    existing[key] = (client_id, cc_id)
                    cc_set += 1
                elif overwrite_existing_cc:
                    conn.execute(
                        "UPDATE clients SET cost_centre_id = ? WHERE id = ?",
                        (cc_id, client_id))
                    existing[key] = (client_id, cc_id)
                    cc_overwritten += 1
                else:
                    unchanged += 1
    # Repoint any voucher / timesheet rows that were stale-linked to
    # something else but should now point at the freshly-created
    # master row.
    for cid, name in newly_created:
        repoint_client_links(cid, name)
    apply_known_client_aliases()
    return {
        "created": created,
        "cc_set": cc_set,
        "cc_overwritten": cc_overwritten,
        "unchanged": unchanged,
        "unknown_cc": unknown_cc,
        "rows_total": len(pairs),
    }


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


def apply_client_master_to_splits() -> int:
    """Fill missing voucher-split cost_centre_id from the client master.

    When a voucher's split has no cost-centre yet but its parent voucher
    is linked to a client whose master row has a cost_centre_id, push
    the client's cost_centre down to the split. Important when Tally
    doesn't tag cost centres at the voucher level — the cc-string
    mapping has nothing to bite on, and the client master is the only
    way to populate the Partner P&L.

    Only fills NULL — explicit cc-string mappings always win.

    (v0.3.47 also propagated manager_id from the client master, but
    that field was retired in v0.3.50 once the Sales/Purchase Register
    Excel began carrying manager+partner per line. The DB column on
    clients remains for legacy data; no new rows write to it.)
    """
    updated = 0
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE voucher_splits "
            "SET cost_centre_id = ("
            "    SELECT c.cost_centre_id FROM clients c "
            "    JOIN vouchers v ON v.id = voucher_splits.voucher_id "
            "    WHERE c.id = v.client_id) "
            "WHERE cost_centre_id IS NULL "
            "  AND EXISTS ("
            "    SELECT 1 FROM clients c "
            "    JOIN vouchers v ON v.id = voucher_splits.voucher_id "
            "    WHERE c.id = v.client_id "
            "      AND c.cost_centre_id IS NOT NULL)")
        updated += cur.rowcount
    return updated


def infer_all_masters() -> dict[str, int]:
    """Run every auto-inference pass over the masters. Idempotent, cheap, and
    safe to call after any operator action or import.

    Order matters: employee cost-centres come from salary; employee managers
    come from timesheet; manager cost-centres come from their employees;
    client cost-centres come from sales voucher splits; finally the client
    master is pushed back down to any voucher splits that are still
    unassigned (the fallback when Tally has no per-line cost centres)."""
    return {
        "employees_cc": infer_employee_cost_centres(),
        "employees_mgr": infer_employee_managers(),
        "managers_cc": infer_manager_cost_centres(),
        "clients_cc": infer_client_cost_centres(),
        "splits_from_client": apply_client_master_to_splits(),
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
    """Permanently delete every source row whose unmapped client name
    matches *raw* (whitespace-insensitive). Use when an unmapped client
    name is bogus / shouldn't be in the MIS at all.

    Covers EVERY table :func:`unresolved_clients` surfaces — sales AND
    purchase vouchers (party_name), timesheet lines and reimbursement rows
    (client_raw). Pre-v0.3.84 it only deleted sales vouchers + timesheet,
    so a purchase-register party or a reimbursement row clicked "Delete"
    in the Review queue removed nothing and silently reappeared on reload.
    Voucher deletes cascade to their splits (FK ON DELETE CASCADE).

    Returns the number of source rows deleted.
    """
    key = norm(raw)
    deleted = 0
    with transaction() as conn:
        # Sales AND purchase vouchers (drop the kind filter).
        rows = conn.execute(
            "SELECT id, party_name FROM vouchers "
            "WHERE client_id IS NULL AND party_name <> ''").fetchall()
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
        rows = conn.execute(
            "SELECT id, client_raw FROM reimbursements "
            "WHERE client_id IS NULL AND client_raw <> ''").fetchall()
        rb_ids = [r["id"] for r in rows if norm(r["client_raw"]) == key]
        if rb_ids:
            ph = ",".join("?" * len(rb_ids))
            conn.execute(
                f"DELETE FROM reimbursements WHERE id IN ({ph})", rb_ids)
            deleted += len(rb_ids)
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

def apply_known_employee_aliases(*, fuzzy_threshold: int = 70) -> int:
    """Fuzzy-link unresolved raw employee names to the employees master.

    Employees are matched by name at calc-time via name + alias, so
    "resolving" an employee just means writing an alias row. This
    function looks at every distinct raw name in salary / timesheet
    that has no exact match, and for each one fuzzy-ranks the active
    employees. When the top score is ≥``fuzzy_threshold`` AND at
    least 5 points clear of the runner-up, the raw name is saved as
    an alias on that employee.

    Returns the number of alias rows newly written.
    """
    return _fuzzy_link_employees(threshold=fuzzy_threshold)


def _fuzzy_link_employees(*, threshold: int = 70, gap: int = 5) -> int:
    """Fuzzy-match every unresolved raw employee name to the master.

    See :func:`_fuzzy_link_clients` for the rationale. Same shape:
    score the raw against all active employees, accept only the clear
    winner above the threshold, and save it as an alias so the next
    import skips the fuzzy pass entirely.
    """
    linked = 0
    with transaction() as conn:
        emps = [(r["id"], r["name"]) for r in conn.execute(
            "SELECT id, name FROM employees WHERE active = 1")]
        if not emps:
            return 0
        norms = {eid: norm_loose(name) for eid, name in emps}
        # Names already known directly or via alias.
        known: set[str] = set()
        for r in conn.execute("SELECT name FROM employees"):
            known.add(norm(r["name"]))
        for r in conn.execute("SELECT alias_text FROM employee_aliases"):
            known.add(norm(r["alias_text"]))
        # Every distinct raw employee name in salary + timesheet.
        raws: set[str] = set()
        for r in conn.execute(
                "SELECT DISTINCT employee_name FROM salary_entries "
                "WHERE employee_name <> ''"):
            raws.add(r["employee_name"])
        for r in conn.execute(
                "SELECT DISTINCT emp_name FROM timesheet_entries "
                "WHERE emp_name <> ''"):
            raws.add(r["emp_name"])
        for raw in raws:
            if norm(raw) in known:
                continue
            target = norm_loose(raw)
            if not target:
                continue
            ranked = process.extract(
                target, norms, scorer=fuzz.token_sort_ratio, limit=3)
            if not ranked:
                continue
            top_score = int(ranked[0][1])
            top_id = ranked[0][2]
            runner = int(ranked[1][1]) if len(ranked) > 1 else 0
            if top_score >= threshold and (top_score - runner) >= gap:
                conn.execute(
                    "INSERT OR IGNORE INTO employee_aliases "
                    "(employee_id, alias_text, source) "
                    "VALUES (?, ?, 'fuzzy')", (top_id, raw))
                linked += 1
    return linked


def bulk_import_employees(
        pairs: list[tuple[str, str]],
        *,
        overwrite_existing_cc: bool = False
) -> dict:
    """Upsert employees from a list of ``(employee_name, cc_code)`` pairs.

    Mirrors :func:`bulk_import_clients`. For each row:

    * Look up the cost-centre by code (case-insensitive).
    * If an employee with the same normalised name already exists, fill
      in their ``default_cost_centre_id`` when it's NULL, leave it alone
      when set (unless ``overwrite_existing_cc=True``).
    * Otherwise insert a new employee row with name + default_cost_centre.

    After the upsert, runs the fuzzy alias pass so any previously
    unresolved raw names in salary/timesheet get linked to the newly
    populated master.

    Returns a dict:
      ``created`` — new employee rows inserted
      ``cc_set`` — existing rows whose NULL cost-centre was filled
      ``cc_overwritten`` — existing rows whose cost-centre changed
      ``unchanged`` — existing rows already matching
      ``unknown_cc`` — list of (name, code) with unknown CC code
      ``rows_total`` — total rows processed
      ``newly_aliased`` — raw names linked via the post-import fuzzy pass
    """
    created = cc_set = cc_overwritten = unchanged = 0
    unknown_cc: list[tuple[str, str]] = []
    with transaction() as conn:
        cc_by_code = {
            r["code"].strip().lower(): r["id"] for r in conn.execute(
                "SELECT id, code FROM cost_centres WHERE active = 1")}
        existing: dict[str, tuple[int, int | None]] = {}
        for r in conn.execute(
                "SELECT id, name, default_cost_centre_id FROM employees"):
            existing[norm(r["name"])] = (r["id"], r["default_cost_centre_id"])
        for raw_name, raw_code in pairs:
            name = (raw_name or "").strip()
            code = (raw_code or "").strip()
            if not name:
                continue
            cc_id = cc_by_code.get(code.lower())
            if cc_id is None:
                unknown_cc.append((name, code))
                continue
            key = norm(name)
            hit = existing.get(key)
            if hit is None:
                eid = conn.execute(
                    "INSERT INTO employees (name, default_cost_centre_id) "
                    "VALUES (?, ?)", (name, cc_id)).lastrowid
                existing[key] = (eid, cc_id)
                created += 1
            else:
                emp_id, current_cc = hit
                if current_cc == cc_id:
                    unchanged += 1
                elif current_cc is None:
                    conn.execute(
                        "UPDATE employees SET default_cost_centre_id = ? "
                        "WHERE id = ?", (cc_id, emp_id))
                    existing[key] = (emp_id, cc_id)
                    cc_set += 1
                elif overwrite_existing_cc:
                    conn.execute(
                        "UPDATE employees SET default_cost_centre_id = ? "
                        "WHERE id = ?", (cc_id, emp_id))
                    existing[key] = (emp_id, cc_id)
                    cc_overwritten += 1
                else:
                    unchanged += 1
    newly_aliased = _fuzzy_link_employees()
    return {
        "created": created,
        "cc_set": cc_set,
        "cc_overwritten": cc_overwritten,
        "unchanged": unchanged,
        "unknown_cc": unknown_cc,
        "rows_total": len(pairs),
        "newly_aliased": newly_aliased,
    }


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


def repoint_employee_links(employee_id: int, employee_name: str) -> int:
    """Drop any ``employee_aliases`` rows whose ``alias_text`` matches
    the given canonical name but points at a different employee.

    Employees are looked up by name at MIS-build time (not stored as
    foreign-keyed columns on salary/timesheet rows), so all we need to
    do here is clean up stale aliases that would still shadow the new
    master row's canonical name in ``emp_index``. The v0.3.58 fix
    that re-orders alias-vs-canonical priority in
    ``_load_masters`` makes this largely belt-and-braces, but
    pruning keeps the alias table tidy.
    """
    key = norm(employee_name)
    if not key:
        return 0
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM employee_aliases "
            "WHERE lower(trim(alias_text)) = ? AND employee_id <> ?",
            (key, employee_id))
        return cur.rowcount or 0


def create_employee(raw: str, name: str, category: str | None,
                     manager_id: int | None,
                     cost_centre_id: int | None,
                     location_id: int | None = None) -> int:
    """Create a new employee master record from a raw name.

    ``location_id`` (v0.3.99) tags the employee's office location — used
    by the Employee Register / overhead location filter. Left NULL the
    employee is excluded whenever a location selection is active (strict,
    v0.3.101); the generated Cover carries a warning listing such records.
    """
    with transaction() as conn:
        eid = conn.execute(
            "INSERT INTO employees (name, category, manager_id, "
            "default_cost_centre_id, location_id) VALUES (?, ?, ?, ?, ?)",
            (name, category, manager_id, cost_centre_id, location_id)).lastrowid
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

        # Second pass: back-fill the MANAGER on splits that already have a
        # cost centre but a blank manager (e.g. a bare "Rajesh Malhotra"
        # resolved to a partner before the manager-matching fix). Only when
        # the mapping's partner matches the split's, so a manager is added
        # without ever moving the cost centre.
        mgr_less = conn.execute(
            "SELECT s.id, s.cost_centre_id AS cc, "
            "       coalesce(s.raw_cost_centre, v.raw_cost_centre) AS raw "
            "FROM voucher_splits s JOIN vouchers v ON v.id = s.voucher_id "
            "WHERE s.manager_id IS NULL AND s.cost_centre_id IS NOT NULL "
            "  AND coalesce(s.raw_cost_centre, v.raw_cost_centre) <> ''"
        ).fetchall()
        mgr_buckets: dict[tuple[int, int], list[int]] = {}
        for s in mgr_less:
            mapping = mappings.get(norm(s["raw"]))
            if mapping and mapping[1] is not None and mapping[0] == s["cc"]:
                mgr_buckets.setdefault((mapping[1], s["cc"]), []).append(s["id"])
        for (mgr_id, _cc), ids in mgr_buckets.items():
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"UPDATE voucher_splits SET manager_id = ? "
                f"WHERE id IN ({placeholders})", (mgr_id, *ids))
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


def _build_partner_manager_lookups(
        conn) -> tuple[dict, dict, dict[int, dict]]:
    """Build the {normalised name → id} lookups for partners and managers.

    Returns ``(partner_lookup, manager_lookup, managers_by_partner)``.
    Each lookup includes:

    * the full canonical name (always)
    * the code (always)
    * **unambiguous** name-part singletons (length ≥ 4, appearing in
      exactly one entry). So "Vishal", "Kothari" → VK; "Shreyans",
      "Dedhia" → SD; but "Mehta" (shared across PM / AM / MS) is
      deliberately excluded — we can't pick one without context.

    ``managers_by_partner`` is ``{cost_centre_id: partner-scoped lookup}``.
    A manager who reports under multiple partners (e.g. Gaurav Siroya
    sits under both Aakash Mehta and Kiran Suvarna) is ambiguous in the
    global manager_lookup — "gaurav" alone can't pick a row. Inside a
    single partner's team, though, that name IS unambiguous: in
    Kiran's team there's only one Gaurav. The matcher uses the
    partner-scoped lookup whenever it already knows the partner side
    of an "X - Y" string, so "Kiran - Gaurav" cleanly resolves to
    GS - KS without an operator prompt.
    """
    partner_lookup = _build_lookup(
        conn,
        "SELECT id, code, name FROM cost_centres "
        "WHERE active = 1 AND cc_type = 'partner'")
    manager_lookup = _build_lookup(
        conn,
        "SELECT id, code, name FROM managers WHERE active = 1")
    partner_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM cost_centres "
        "WHERE active = 1 AND cc_type = 'partner'")]
    managers_by_partner: dict[int, dict] = {}
    for cc_id in partner_ids:
        managers_by_partner[cc_id] = _build_lookup(
            conn,
            "SELECT id, code, name FROM managers "
            "WHERE active = 1 AND cost_centre_id = ?",
            (cc_id,))
    # manager_id → home partner cost centre. Lets a bare manager-name CC
    # string ("Rajesh Malhotra") resolve to BOTH the manager and that
    # manager's partner cost centre.
    manager_cc: dict[int, int | None] = {
        r["id"]: r["cost_centre_id"]
        for r in conn.execute(
            "SELECT id, cost_centre_id FROM managers WHERE active = 1")}
    return partner_lookup, manager_lookup, managers_by_partner, manager_cc


def _build_lookup(conn, sql: str, params: tuple = ()) -> dict[str, int]:
    """Helper: build the lookup dict for one master table."""
    rows = list(conn.execute(sql, params))
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
                          managers_by_partner: dict[int, dict] | None = None,
                          min_score: int = _MIN_SCORE,
                          manager_cc: dict[int, int | None] | None = None
                          ) -> tuple[int | None, int | None, int]:
    """Match a single CC string. Returns ``(cc_id, mgr_id, score)``.

    Same logic as :func:`auto_match_cc_strings` distilled to one string.
    *min_score* controls how confident we need to be — 70 is the auto-
    apply threshold; 50 is what the SplitEditor uses for *suggestions*
    where the operator will confirm before saving.

    When ``managers_by_partner`` is given and the partner side has been
    resolved, the manager side is matched ONLY against that partner's
    team. This disambiguates names like "Gaurav" that appear in multiple
    partners' teams ("Kiran - Gaurav" → GS-KS, not GS-AM) and prevents a
    manager from another partner being attached ("Jalpesh - Umesh" → JV
    with NO manager, never "UV - AM"). The global lookup is used only when
    no partner was resolved.
    """
    cleaned = norm(_HONORIFICS.sub("", (raw or "").strip()))
    if not cleaned:
        return None, None, 0
    cc_id: int | None = None
    mgr_id: int | None = None
    best_score = 0

    def _match_mgr(text: str, partner_cc_id: int | None) -> int | None:
        """Find a manager id for *text*, scoped to the resolved partner.

        A manager record is partner-specific, so when the partner is known
        the manager MUST come from that partner's team — we never fall back
        to a global match that could pin a manager from a different partner
        (e.g. "Jalpesh - Umesh" wrongly attaching "UV - AM" under JV). The
        global lookup is only used when no partner was resolved at all.
        """
        if (managers_by_partner is not None
                and partner_cc_id is not None
                and partner_cc_id in managers_by_partner):
            m_id, m_score = _best_match(
                text, managers_by_partner[partner_cc_id])
            return m_id if m_score >= min_score else None
        m_id, m_score = _best_match(text, manager_lookup)
        return m_id if m_score >= min_score else None

    # "X - Y" — try both as the partner side.
    parts = _NAME_SEP.split(cleaned, maxsplit=1)
    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        l_id, l_score = _best_match(left, partner_lookup)
        r_id, r_score = _best_match(right, partner_lookup)
        if r_score >= l_score and r_score >= min_score:
            cc_id, best_score = r_id, r_score
            mgr_id = _match_mgr(left, cc_id)
        elif l_score >= min_score:
            cc_id, best_score = l_id, l_score
            mgr_id = _match_mgr(right, cc_id)
    # Plain — try the whole string as a partner.
    if cc_id is None:
        id_w, score_w = _best_match(cleaned, partner_lookup)
        if score_w >= min_score:
            cc_id, best_score = id_w, score_w
    # Bare manager name (Tally tagged the CC with just "Rajesh Malhotra",
    # no "partner - manager"). If the whole string matches a MANAGER at
    # least as well as any partner guess, adopt that manager AND their home
    # partner cost centre. A strong, exact manager match (100) rightly beats
    # a weak fuzzy partner match (e.g. 64) that only coincidentally lands on
    # the right partner — and crucially it fills in the manager.
    if manager_cc is not None and mgr_id is None:
        m_id, m_score = _best_match(cleaned, manager_lookup)
        if (m_id is not None and m_score >= min_score
                and m_score >= best_score
                and manager_cc.get(m_id) is not None):
            cc_id = manager_cc[m_id]
            mgr_id = m_id
            best_score = m_score
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
        partner_lookup, manager_lookup, managers_by_partner, manager_cc = \
            _build_partner_manager_lookups(conn)
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
                raw, partner_lookup, manager_lookup,
                managers_by_partner=managers_by_partner, min_score=50,
                manager_cc=manager_cc)
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
        partner_lookup, manager_lookup, managers_by_partner, manager_cc = \
            _build_partner_manager_lookups(conn)
    return _match_one_cc_string(
        raw, partner_lookup, manager_lookup,
        managers_by_partner=managers_by_partner, min_score=min_score,
        manager_cc=manager_cc)


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
        partner_lookup, manager_lookup, managers_by_partner, manager_cc = \
            _build_partner_manager_lookups(conn)

    if not partner_lookup:
        return 0

    new_mappings: list[tuple[str, int, int | None]] = []
    for item in unresolved_cc_strings():
        raw = item["raw"]
        cc_id, mgr_id, _score = _match_one_cc_string(
            raw, partner_lookup, manager_lookup,
            managers_by_partner=managers_by_partner, min_score=_MIN_SCORE,
            manager_cc=manager_cc)
        if cc_id is not None:
            new_mappings.append((raw, cc_id, mgr_id))

    # Back-fill the MANAGER on existing mappings that resolved a partner
    # but left the manager blank — e.g. a bare "Rajesh Malhotra" mapped
    # pre-fix. Only when the matched manager's home partner EQUALS the
    # already-saved partner, so we add the manager without ever moving a
    # cost centre (zero regression to existing partner assignments).
    upgrades: list[tuple[str, int]] = []
    with transaction() as conn:
        manager_less = conn.execute(
            "SELECT raw_text, cost_centre_id FROM cc_string_mappings "
            "WHERE active = 1 AND manager_id IS NULL "
            "AND cost_centre_id IS NOT NULL").fetchall()
    for r in manager_less:
        cc_id, mgr_id, _score = _match_one_cc_string(
            r["raw_text"], partner_lookup, manager_lookup,
            managers_by_partner=managers_by_partner, min_score=_MIN_SCORE,
            manager_cc=manager_cc)
        if mgr_id is not None and cc_id == r["cost_centre_id"]:
            upgrades.append((r["raw_text"], mgr_id))

    if not new_mappings and not upgrades:
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
        for raw, mgr_id in upgrades:
            conn.execute(
                "UPDATE cc_string_mappings SET manager_id = ? "
                "WHERE lower(trim(raw_text)) = ? AND manager_id IS NULL",
                (mgr_id, raw.strip().lower()))
    # Apply the new / upgraded mappings to existing voucher splits.
    apply_known_cc_string_mappings()
    infer_all_masters()
    return len(new_mappings) + len(upgrades)


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
