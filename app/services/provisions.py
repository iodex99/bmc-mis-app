"""Provision costs — a direct cost a cost centre expects to incur (tied to
a client) but hasn't yet. Booked for a month, shown as a direct cost in the
MIS, and carried forward until adjustments bring the remaining to zero.

The master UI shows the CURRENT outstanding remaining (amount − all
adjustments). The MIS (``calc._build_provision_facts``) recomputes the
remaining *as of the reporting month* so a provision shrinks period by
period as real expenses are recorded against it.
"""

from __future__ import annotations

from ..database import transaction


def list_provisions() -> list[dict]:
    """Every provision with its entity / client labels and the total
    adjusted + remaining (across all adjustments)."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT p.*, e.name AS entity_name, c.canonical_name AS client_name, "
            "  (SELECT COALESCE(SUM(a.amount), 0) FROM provision_adjustments a "
            "     WHERE a.provision_id = p.id) AS adjusted "
            "FROM provisions p "
            "LEFT JOIN entities e ON e.id = p.entity_id "
            "LEFT JOIN clients c ON c.id = p.client_id "
            "WHERE p.active = 1 "
            "ORDER BY p.period DESC, p.id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["remaining"] = round(float(d["amount"] or 0) - float(d["adjusted"] or 0), 2)
        out.append(d)
    return out


def add_provision(period: str, entity_id: int | None, client_id: int | None,
                  amount: float, note: str = "") -> int:
    with transaction() as conn:
        return conn.execute(
            "INSERT INTO provisions (period, entity_id, client_id, amount, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (period, entity_id, client_id, amount, note or None)).lastrowid


def update_provision(prov_id: int, period: str, entity_id: int | None,
                     client_id: int | None, amount: float,
                     note: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE provisions SET period = ?, entity_id = ?, client_id = ?, "
            "amount = ?, note = ? WHERE id = ?",
            (period, entity_id, client_id, amount, note or None, prov_id))


def delete_provision(prov_id: int) -> None:
    """Hard delete the provision and its adjustments (FK cascade)."""
    with transaction() as conn:
        conn.execute("DELETE FROM provision_adjustments WHERE provision_id = ?",
                     (prov_id,))
        conn.execute("DELETE FROM provisions WHERE id = ?", (prov_id,))


def list_adjustments(prov_id: int) -> list[dict]:
    with transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM provision_adjustments WHERE provision_id = ? "
            "ORDER BY adjusted_period, id", (prov_id,))]


def add_adjustment(prov_id: int, amount: float, adjusted_period: str,
                   note: str = "") -> int:
    with transaction() as conn:
        return conn.execute(
            "INSERT INTO provision_adjustments "
            "(provision_id, amount, adjusted_period, note) VALUES (?, ?, ?, ?)",
            (prov_id, amount, adjusted_period, note or None)).lastrowid
