"""Voucher & split queries used by the Review page and the calculation engine."""

from __future__ import annotations

from ..database import transaction


def list_periods() -> list[str]:
    """All calendar-month periods that have any data, newest first."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT period FROM vouchers WHERE period IS NOT NULL "
            "UNION SELECT period FROM timesheet_entries WHERE period IS NOT NULL "
            "UNION SELECT period FROM salary_entries WHERE period IS NOT NULL "
            "ORDER BY period DESC")
        return [r["period"] for r in rows]


def list_vouchers(entity_id: int | None = None, period: str | None = None,
                  kind: str | None = None) -> list[dict]:
    """Vouchers with resolved client name and a one-line split summary."""
    sql = [
        "SELECT v.*, c.canonical_name AS client_name,",
        "  (SELECT COUNT(*) FROM voucher_splits s WHERE s.voucher_id = v.id) AS n_splits,",
        "  (SELECT COUNT(*) FROM voucher_splits s WHERE s.voucher_id = v.id",
        "     AND s.cost_centre_id IS NULL) AS n_unassigned",
        "FROM vouchers v LEFT JOIN clients c ON c.id = v.client_id WHERE 1=1",
    ]
    params: list = []
    if entity_id is not None:
        sql.append("AND v.entity_id = ?")
        params.append(entity_id)
    if period:
        sql.append("AND v.period = ?")
        params.append(period)
    if kind:
        sql.append("AND v.kind = ?")
        params.append(kind)
    sql.append("ORDER BY v.txn_date, v.id")
    with transaction() as conn:
        return [dict(r) for r in conn.execute(" ".join(sql), params)]


def get_splits(voucher_id: int) -> list[dict]:
    """All splits of a voucher."""
    with transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM voucher_splits WHERE voucher_id = ? ORDER BY id",
            (voucher_id,))]


def save_splits(voucher_id: int, splits: list[dict]) -> None:
    """Replace a voucher's splits with the supplied list."""
    with transaction() as conn:
        conn.execute("DELETE FROM voucher_splits WHERE voucher_id = ?",
                     (voucher_id,))
        for s in splits:
            conn.execute(
                "INSERT INTO voucher_splits (voucher_id, amount, cost_centre_id, "
                "manager_id, service_id, note) VALUES (?, ?, ?, ?, ?, ?)",
                (voucher_id, s.get("amount", 0.0), s.get("cost_centre_id"),
                 s.get("manager_id"), s.get("service_id"), s.get("note")))


def split_stats() -> dict:
    """Counts used by the Review dashboard."""
    with transaction() as conn:
        total = conn.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0]
        unassigned = conn.execute(
            "SELECT COUNT(DISTINCT voucher_id) FROM voucher_splits "
            "WHERE cost_centre_id IS NULL").fetchone()[0]
    return {"vouchers": total, "vouchers_unassigned": unassigned}
