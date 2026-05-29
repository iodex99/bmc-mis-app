"""Read-only queries that power the Records page.

The Records page is the operator's window into the historical data stored in
``mis.db``: every imported salary row, every timesheet line, every import
batch — period-tagged and fully searchable.
"""

from __future__ import annotations

from ..database import transaction


# --- import batches ---------------------------------------------------------

def list_import_batches() -> list[dict]:
    """Every import batch, newest first, with row counts per type."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT b.id, b.imported_at, b.entity_id, b.file_type, b.period, "
            "  b.file_name, b.status, "
            "  (SELECT COUNT(*) FROM vouchers v WHERE v.batch_id = b.id) AS vch, "
            "  (SELECT COUNT(*) FROM timesheet_entries t WHERE t.batch_id = b.id) AS ts, "
            "  (SELECT COUNT(*) FROM salary_entries s WHERE s.batch_id = b.id) AS sal "
            "FROM import_batches b ORDER BY b.imported_at DESC, b.id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_import_batch(batch_id: int) -> None:
    """Delete a batch and every row it created (vouchers cascade to splits).
    Saved column-mapping templates are preserved."""
    with transaction() as conn:
        # Foreign keys with ON DELETE CASCADE handle the dependants.
        conn.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))


# --- periods ----------------------------------------------------------------

def list_salary_periods() -> list[str]:
    with transaction() as conn:
        return [r["period"] for r in conn.execute(
            "SELECT DISTINCT period FROM salary_entries "
            "WHERE period IS NOT NULL ORDER BY period DESC")]


def list_timesheet_periods() -> list[str]:
    with transaction() as conn:
        return [r["period"] for r in conn.execute(
            "SELECT DISTINCT period FROM timesheet_entries "
            "WHERE period IS NOT NULL ORDER BY period DESC")]


# --- salary -----------------------------------------------------------------

def list_salary(period: str | None = None,
                employee_q: str = "") -> list[dict]:
    sql = (
        "SELECT s.period, s.employee_name, "
        "  cc.code AS cc_code, cc.name AS cc_name, "
        "  e.name AS entity_name, "
        "  s.category, s.salary_paid, s.reimbursement, "
        "  s.raw_cost_centre, s.raw_entity "
        "FROM salary_entries s "
        "LEFT JOIN cost_centres cc ON cc.id = s.cost_centre_id "
        "LEFT JOIN entities e ON e.id = s.entity_id "
        "WHERE 1=1")
    params: list = []
    if period:
        sql += " AND s.period = ?"
        params.append(period)
    if employee_q:
        sql += " AND lower(s.employee_name) LIKE ?"
        params.append(f"%{employee_q.lower()}%")
    sql += " ORDER BY s.period DESC, s.employee_name"
    with transaction() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def salary_totals(period: str | None = None,
                  employee_q: str = "") -> dict:
    sql_where = "WHERE 1=1"
    params: list = []
    if period:
        sql_where += " AND period = ?"
        params.append(period)
    if employee_q:
        sql_where += " AND lower(employee_name) LIKE ?"
        params.append(f"%{employee_q.lower()}%")
    with transaction() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS n, "
            f"  COUNT(DISTINCT lower(trim(employee_name))) AS people, "
            f"  COALESCE(SUM(salary_paid), 0) AS salary, "
            f"  COALESCE(SUM(reimbursement), 0) AS reimb "
            f"FROM salary_entries {sql_where}", params).fetchone()
    return dict(row) if row else {}


# --- timesheet --------------------------------------------------------------

def list_timesheet(period: str | None = None, employee_q: str = "",
                   client_q: str = "") -> list[dict]:
    sql = (
        "SELECT t.txn_date, t.emp_name, t.client_raw, "
        "  c.canonical_name AS client_name, "
        "  t.task, t.hours, t.reporting_manager, t.is_billable, t.description "
        "FROM timesheet_entries t "
        "LEFT JOIN clients c ON c.id = t.client_id "
        "WHERE 1=1")
    params: list = []
    if period:
        sql += " AND t.period = ?"
        params.append(period)
    if employee_q:
        sql += " AND lower(t.emp_name) LIKE ?"
        params.append(f"%{employee_q.lower()}%")
    if client_q:
        sql += (" AND (lower(t.client_raw) LIKE ? "
                "OR lower(c.canonical_name) LIKE ?)")
        like = f"%{client_q.lower()}%"
        params.extend([like, like])
    sql += " ORDER BY t.txn_date, t.emp_name"
    with transaction() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def timesheet_totals(period: str | None = None, employee_q: str = "",
                     client_q: str = "") -> dict:
    sql_where = "WHERE 1=1"
    params: list = []
    if period:
        sql_where += " AND period = ?"
        params.append(period)
    if employee_q:
        sql_where += " AND lower(emp_name) LIKE ?"
        params.append(f"%{employee_q.lower()}%")
    if client_q:
        sql_where += " AND lower(client_raw) LIKE ?"
        params.append(f"%{client_q.lower()}%")
    with transaction() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS n, "
            f"  COUNT(DISTINCT lower(trim(emp_name))) AS people, "
            f"  COUNT(DISTINCT lower(trim(client_raw))) AS clients, "
            f"  COALESCE(SUM(hours), 0) AS hours, "
            f"  COALESCE(SUM(CASE WHEN is_billable=1 THEN hours ELSE 0 END), 0) "
            f"     AS billable_hours "
            f"FROM timesheet_entries {sql_where}", params).fetchone()
    return dict(row) if row else {}
