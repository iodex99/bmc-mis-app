"""Wipe imported / transactional data and reset to a clean import state.

The schema is preserved (so any pending migrations stay applied). Master
data — entities, cost centres, managers, clients, employees, services,
targets, plus their aliases and saved mappings — is also preserved so
the operator doesn't lose hours of one-off setup work every time they
clear out a stale import.

What gets wiped:

* ``import_batches`` and every voucher / timesheet / salary row that
  was staged by an import,
* the resulting ``voucher_splits``.

What is preserved:

* Every row in the Master Data tabs (Entities, Cost Centres, Managers,
  Employees, Clients, Services, Annual Targets) and their alias
  tables — the operator built these up via bulk-import + manual
  curation.
* ``cc_string_mappings`` — saved CC-string → (partner, manager)
  resolutions the operator confirmed during Review.
* ``column_templates`` and ``app_settings`` — UI / parser config.

After the wipe, ``_seed`` is still called as a safety net: it no-ops
when entities already exist, but re-seeds the firm masters on the
exceedingly rare case where a previous abort left the DB empty.

Triggered from the operator-facing 'Clear all data' button in Settings.
"""

from __future__ import annotations

from ..database import _seed, transaction


# Tables that hold IMPORTED / TRANSACTIONAL data — the only ones the
# reset should empty. Everything else is master data or config and
# survives the wipe.
_TRANSACTIONAL_TABLES = (
    "voucher_splits",
    "vouchers",
    "timesheet_entries",
    "salary_entries",
    "import_batches",
)


def reset_all_data() -> None:
    """Delete all imported data; keep every master table intact."""
    with transaction() as conn:
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall()}

        conn.execute("PRAGMA foreign_keys = OFF")
        for tbl in _TRANSACTIONAL_TABLES:
            if tbl in existing:
                conn.execute(f'DELETE FROM "{tbl}"')
        # Reset AUTOINCREMENT counters only for the tables we wiped so
        # the next batch_id / voucher_id starts at 1 again.
        try:
            placeholders = ",".join("?" * len(_TRANSACTIONAL_TABLES))
            conn.execute(
                f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
                _TRANSACTIONAL_TABLES)
        except Exception:
            # sqlite_sequence may not exist if no AUTOINCREMENT was used yet.
            pass
        conn.execute("PRAGMA foreign_keys = ON")

        # No-op when master tables already populated; insurance against
        # a half-broken database that somehow lost its masters.
        _seed(conn)
