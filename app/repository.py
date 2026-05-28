"""Generic data-access helpers over the SQLite database.

Table names passed in always come from the fixed master-data specs in the UI
layer (never user input), so building SQL with them is safe.
"""

from __future__ import annotations

from typing import Any

from .database import transaction

# How each foreign-key target renders in dropdowns / display columns.
_FK_LABEL = {
    "cost_centres": "code || ' — ' || name",
    "managers": "code || ' — ' || name",
    "entities": "name",
    "services": "name",
    "clients": "canonical_name",
}


def fetch_all(table: str, include_inactive: bool = True,
              order_by: str = "id") -> list[dict[str, Any]]:
    """Return every row of *table* as dicts (optionally only active rows)."""
    sql = f"SELECT * FROM {table}"
    if not include_inactive and _has_active(table):
        sql += " WHERE active = 1"
    sql += f" ORDER BY {order_by}"
    with transaction() as conn:
        return [dict(r) for r in conn.execute(sql)]


def insert(table: str, data: dict[str, Any]) -> int:
    """Insert a row; return its new id."""
    cols = ", ".join(data)
    placeholders = ", ".join("?" * len(data))
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        return int(cur.lastrowid)


def update(table: str, row_id: int, data: dict[str, Any]) -> None:
    """Update one row by id."""
    assignments = ", ".join(f"{k} = ?" for k in data)
    with transaction() as conn:
        conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            (*data.values(), row_id),
        )


def set_active(table: str, row_id: int, active: bool) -> None:
    """Soft delete / restore a master record."""
    update(table, row_id, {"active": 1 if active else 0})


def delete(table: str, row_id: int) -> None:
    """Hard delete a row (used for tables without an ``active`` flag)."""
    with transaction() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))


def fk_options(table: str, include_inactive: bool = False) -> list[tuple[int, str]]:
    """Return ``(id, label)`` pairs for populating a foreign-key dropdown."""
    label = _FK_LABEL.get(table, "name")
    sql = f"SELECT id, {label} AS label FROM {table}"
    if not include_inactive and _has_active(table):
        sql += " WHERE active = 1"
    sql += " ORDER BY label"
    with transaction() as conn:
        return [(r["id"], r["label"]) for r in conn.execute(sql)]


def fk_label_map(table: str) -> dict[int, str]:
    """Return ``{id: label}`` for every row of an FK table (incl. inactive)."""
    label = _FK_LABEL.get(table, "name")
    with transaction() as conn:
        return {r["id"]: r["label"]
                for r in conn.execute(f"SELECT id, {label} AS label FROM {table}")}


def _has_active(table: str) -> bool:
    with transaction() as conn:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    return "active" in cols
