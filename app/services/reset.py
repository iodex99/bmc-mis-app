"""Wipe all user data and reset to factory state.

The schema is preserved (so any pending migrations stay applied) — only the
*rows* are deleted. After the wipe, the seed runs again to restore the firm's
known entities, cost centres and managers.

Triggered only from the operator-facing 'Clear all data' button in Settings.
"""

from __future__ import annotations

from ..database import _seed, transaction


def reset_all_data() -> None:
    """Delete every row from every user table, then re-seed the firm masters."""
    with transaction() as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall()]

        conn.execute("PRAGMA foreign_keys = OFF")
        for tbl in tables:
            conn.execute(f'DELETE FROM "{tbl}"')
        try:
            conn.execute("DELETE FROM sqlite_sequence")
        except Exception:
            # sqlite_sequence may not exist if no AUTOINCREMENT was used yet.
            pass
        conn.execute("PRAGMA foreign_keys = ON")

        # Restore the firm's known entities, cost centres and managers.
        _seed(conn)
