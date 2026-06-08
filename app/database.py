"""SQLite database layer: schema migrations, connections and first-run seeding.

Schema changes are expressed as ordered migrations keyed by version number.
On every app launch :func:`init_db` advances the database from whatever version
it is on to the latest. The user's data is never deleted — migrations only add
tables / columns / data.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from . import config

# ---------------------------------------------------------------------------
# Migrations.
#
# Each migration is a tuple (version, sql). They run in order; the engine sets
# PRAGMA user_version to the migration's number after it succeeds. Adding a
# new schema change = append a new tuple here with the next integer.
# DO NOT renumber or remove past migrations — installed copies depend on them.
# ---------------------------------------------------------------------------

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS entities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS entity_aliases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id   INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            alias       TEXT NOT NULL,
            UNIQUE(alias)
        );

        CREATE TABLE IF NOT EXISTS cost_centres (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            cc_type     TEXT NOT NULL DEFAULT 'partner',
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS managers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT NOT NULL UNIQUE,
            name            TEXT NOT NULL,
            cost_centre_id  INTEGER REFERENCES cost_centres(id),
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS employees (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code                TEXT,
            name                    TEXT NOT NULL,
            category                TEXT,
            manager_id              INTEGER REFERENCES managers(id),
            default_cost_centre_id  INTEGER REFERENCES cost_centres(id),
            active                  INTEGER NOT NULL DEFAULT 1,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(name)
        );

        CREATE TABLE IF NOT EXISTS clients (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name  TEXT NOT NULL UNIQUE,
            cost_centre_id  INTEGER REFERENCES cost_centres(id),
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS client_aliases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            alias_text  TEXT NOT NULL,
            source      TEXT,
            UNIQUE(alias_text, source)
        );

        CREATE TABLE IF NOT EXISTS services (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL UNIQUE,
            active  INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS targets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            financial_year  TEXT NOT NULL,
            cost_centre_id  INTEGER NOT NULL REFERENCES cost_centres(id),
            target_amount   REAL NOT NULL DEFAULT 0,
            UNIQUE(financial_year, cost_centre_id)
        );

        CREATE TABLE IF NOT EXISTS import_batches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id   INTEGER REFERENCES entities(id),
            file_type   TEXT NOT NULL,
            file_name   TEXT,
            period      TEXT,
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            status      TEXT NOT NULL DEFAULT 'staged'
        );

        CREATE TABLE IF NOT EXISTS vouchers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
            entity_id       INTEGER REFERENCES entities(id),
            txn_date        TEXT,
            period          TEXT,
            vch_type        TEXT,
            vch_no          TEXT,
            party_name      TEXT,
            client_id       INTEGER REFERENCES clients(id),
            gross_amount    REAL DEFAULT 0,
            tax_amount      REAL DEFAULT 0,
            net_amount      REAL DEFAULT 0,
            description     TEXT,
            ledger_head     TEXT,
            raw_cost_centre TEXT,
            kind            TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS voucher_splits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id      INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
            amount          REAL NOT NULL DEFAULT 0,
            cost_centre_id  INTEGER REFERENCES cost_centres(id),
            manager_id      INTEGER REFERENCES managers(id),
            service_id      INTEGER REFERENCES services(id),
            note            TEXT
        );

        CREATE TABLE IF NOT EXISTS timesheet_entries (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id            INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
            emp_code            TEXT,
            emp_name            TEXT,
            txn_date            TEXT,
            period              TEXT,
            client_raw          TEXT,
            client_id           INTEGER REFERENCES clients(id),
            task                TEXT,
            hours               REAL DEFAULT 0,
            day_fraction        REAL DEFAULT 0,
            reporting_manager   TEXT,
            description         TEXT,
            is_billable         INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS salary_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
            period          TEXT,
            employee_name   TEXT,
            cost_centre_id  INTEGER REFERENCES cost_centres(id),
            raw_cost_centre TEXT,
            entity_id       INTEGER REFERENCES entities(id),
            raw_entity      TEXT,
            category        TEXT,
            salary_paid     REAL DEFAULT 0,
            reimbursement   REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS column_templates (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT,
            entity_id           INTEGER REFERENCES entities(id),
            file_type           TEXT NOT NULL,
            layout_signature    TEXT NOT NULL,
            column_map          TEXT NOT NULL,
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(file_type, layout_signature)
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key     TEXT PRIMARY KEY,
            value   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_vouchers_period   ON vouchers(period);
        CREATE INDEX IF NOT EXISTS idx_vouchers_entity   ON vouchers(entity_id);
        CREATE INDEX IF NOT EXISTS idx_splits_voucher    ON voucher_splits(voucher_id);
        CREATE INDEX IF NOT EXISTS idx_timesheet_period  ON timesheet_entries(period);
        CREATE INDEX IF NOT EXISTS idx_salary_period     ON salary_entries(period);
        CREATE INDEX IF NOT EXISTS idx_client_alias      ON client_aliases(alias_text);
    """),
    (2, """
        CREATE TABLE IF NOT EXISTS employee_aliases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            alias_text  TEXT NOT NULL,
            source      TEXT,
            UNIQUE(alias_text, source)
        );
    """),
    (3, """
        -- Maps a raw Tally 'Cost Center' string (e.g. 'Mr. Shreyans Dedhia',
        -- 'Prashant - Shreyans') to a (cost_centre, manager) pair. Used by
        -- the sales-register import — operator maps each distinct string
        -- once and the resolution is remembered.
        CREATE TABLE IF NOT EXISTS cc_string_mappings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text        TEXT NOT NULL UNIQUE,
            cost_centre_id  INTEGER REFERENCES cost_centres(id),
            manager_id      INTEGER REFERENCES managers(id),
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """),
    (4, """
        -- Re-bucket existing timesheet rows from the calendar month they
        -- were imported under to the firm's 21st→20th MIS month. Day ≤ 20
        -- stays in the current month; day ≥ 21 rolls into the next month.
        UPDATE timesheet_entries
        SET period = CASE
            WHEN CAST(strftime('%d', txn_date) AS INTEGER) <= 20
                THEN strftime('%Y-%m', txn_date)
            ELSE strftime('%Y-%m', date(txn_date, '+1 month'))
        END
        WHERE txn_date IS NOT NULL AND txn_date <> '';
    """),
    (5, """
        -- Per-line cost-centre attribution: when the Tally voucher-dump
        -- parser splits a multi-service voucher across different partners,
        -- each split now carries its own raw cost-centre string. Back-fill
        -- existing rows from the parent voucher so the resolution sweeps
        -- keep working over pre-v5 data.
        ALTER TABLE voucher_splits ADD COLUMN raw_cost_centre TEXT;
        UPDATE voucher_splits
        SET raw_cost_centre = (
            SELECT v.raw_cost_centre FROM vouchers v
            WHERE v.id = voucher_splits.voucher_id)
        WHERE raw_cost_centre IS NULL;

        -- Dedup support: a fast index over the natural key. We do *not*
        -- add a UNIQUE constraint here (would break on legacy data with
        -- duplicates); the app-level check in commit.py handles dedup.
        CREATE INDEX IF NOT EXISTS idx_vouchers_dedup
            ON vouchers(entity_id, kind, vch_no);
    """),
    (6, """
        -- Add manager to client master. Clients already had a cost-centre
        -- (partner) link; the operator can now also bind a default manager
        -- so the client's voucher splits inherit BOTH cost-centre and
        -- manager — same shape as cc_string_mappings. Critical when a
        -- firm's Tally has no cost-centre tagging at the voucher level
        -- (everything flows through the client master instead).
        ALTER TABLE clients ADD COLUMN manager_id INTEGER REFERENCES managers(id);
    """),
    # When you change the schema, append a new (version, sql) tuple here.
]


def latest_version() -> int:
    return MIGRATIONS[-1][0] if MIGRATIONS else 0


# --- Connection management ---------------------------------------------------

def connect() -> sqlite3.Connection:
    """Open a connection to the MIS database with sane pragmas applied."""
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection that commits on success."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- Initialisation ----------------------------------------------------------

def init_db() -> None:
    """Run pending migrations, then seed first-run data."""
    conn = connect()
    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for version, sql in MIGRATIONS:
            if version > current:
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {version}")
                conn.commit()
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    """Populate the firm's known entities, cost centres and managers once."""
    if conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0] > 0:
        return

    entities = [
        "Bilimoria Mehta & Co.",
        "Bilimoria Mehta Corporate",
        "MASD & CO",
        "MASD Advisors",
        "Qualzen",
        "Bilimoria Mehta & Co. (Bangalore)",
    ]
    for name in entities:
        conn.execute("INSERT INTO entities(name) VALUES (?)", (name,))

    for alias, ent in [
        ("Bilimoria", "Bilimoria Mehta & Co."),
        ("Corporate", "Bilimoria Mehta Corporate"),
        ("Advisors", "MASD Advisors"),
    ]:
        row = conn.execute("SELECT id FROM entities WHERE name = ?",
                           (ent,)).fetchone()
        if row:
            conn.execute(
                "INSERT OR IGNORE INTO entity_aliases(entity_id, alias) "
                "VALUES (?, ?)", (row["id"], alias))

    partners = [
        ("PM", "Prakash Mehta"), ("KS", "Kiran Suvarna"),
        ("JV", "Jalpesh Vora"), ("AM", "Aakash Mehta"),
        ("SD", "Shreyans Dedhia"), ("VK", "Vishal Kothari"),
        ("MS", "Megha Mehta"), ("AL", "Abhilash Lapasia"),
    ]
    for code, name in partners:
        conn.execute(
            "INSERT INTO cost_centres(code, name, cc_type) "
            "VALUES (?, ?, 'partner')", (code, name))
    conn.execute(
        "INSERT INTO cost_centres(code, name, cc_type) "
        "VALUES ('Office', 'Office / Firm Overheads', 'office')")

    managers = [
        ("RM", "Rajesh Malhotra"), ("SR", "Sahil Rathod"),
        ("UV", "Umesh Vishwakarma"), ("GS", "Gaurav Siroya"),
    ]
    for code, name in managers:
        conn.execute("INSERT INTO managers(code, name) VALUES (?, ?)",
                     (code, name))


if __name__ == "__main__":
    init_db()
    with transaction() as c:
        for tbl in ("entities", "cost_centres", "managers"):
            n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"{tbl}: {n} rows")
        v = c.execute("PRAGMA user_version").fetchone()[0]
        print(f"schema version: {v}")
