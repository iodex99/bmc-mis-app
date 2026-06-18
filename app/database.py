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
    (7, """
        -- Backfill the firm's 10-manager master into any existing database.
        -- The v0.3.49 _first_run_seed got this right for fresh installs,
        -- but databases initialised before that version still hold the
        -- 4-row starter set. This migration adds the missing rows
        -- idempotently (INSERT OR IGNORE on the compound code column,
        -- which is UNIQUE) and binds each to its partner cost-centre.
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'RM - PM', 'Rajesh Malhotra',   id FROM cost_centres WHERE code='PM';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'SR - AM', 'Sahil Rathod',      id FROM cost_centres WHERE code='AM';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'UV - AM', 'Umesh Vishwakarma', id FROM cost_centres WHERE code='AM';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'GS - KS', 'Gaurav Siroya',     id FROM cost_centres WHERE code='KS';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'BS - SD', 'Bhavya Shah',       id FROM cost_centres WHERE code='SD';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'GS - AM', 'Gaurav Siroya',     id FROM cost_centres WHERE code='AM';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'BS - JV', 'Bhavik Shah',       id FROM cost_centres WHERE code='JV';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'KS - SD', 'Kiwa Shah',         id FROM cost_centres WHERE code='SD';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'HD - JV', 'Hitesh Doshi',      id FROM cost_centres WHERE code='JV';
        INSERT OR IGNORE INTO managers(code, name, cost_centre_id)
            SELECT 'RR - VK', 'Rutwick Ruparelia', id FROM cost_centres WHERE code='VK';
    """),
    (8, """
        -- Entity letterhead aliases. Tally exports identify the entity
        -- via the letterhead (company name + address); auto-detection
        -- has to handle two awkward cases that v0.3.51 couldn't:
        --
        --  1. The Bangalore branch ('Bilimoria Mehta & Co. (Bangalore)')
        --     uses the SAME company name as the Mumbai HQ — only the
        --     address line distinguishes them. Adding 'Bengaluru' /
        --     'Bangalore' / 'Jayanagar' as aliases for the Bangalore
        --     entity lets the letterhead-scan matcher pick the right
        --     one off the address.
        --
        --  2. The Corporate entity is in the master as
        --     'Bilimoria Mehta Corporate' but in Tally it's named
        --     'BMC Corporate Solutions Pvt Ltd' — too different for
        --     fuzzy match. Adding explicit aliases for the legal name
        --     and the 'BMC Corporate' short form bridges that gap.
        --
        --  3. MASD entities export with their full legal names
        --     ('MASD ADVISORS PRIVATE LIMITED', 'MASD & CO LLP') —
        --     fuzzy already catches these but explicit aliases are
        --     faster, cheaper, and unambiguous.
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'Bengaluru' FROM entities WHERE name='Bilimoria Mehta & Co. (Bangalore)';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'Bangalore' FROM entities WHERE name='Bilimoria Mehta & Co. (Bangalore)';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'Jayanagar' FROM entities WHERE name='Bilimoria Mehta & Co. (Bangalore)';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'BMC Corporate Solutions Pvt Ltd' FROM entities WHERE name='Bilimoria Mehta Corporate';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'BMC Corporate Solutions' FROM entities WHERE name='Bilimoria Mehta Corporate';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'BMC Corporate' FROM entities WHERE name='Bilimoria Mehta Corporate';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'MASD ADVISORS PRIVATE LIMITED' FROM entities WHERE name='MASD Advisors';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'MASD Advisors Private Limited' FROM entities WHERE name='MASD Advisors';
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias)
            SELECT id, 'MASD & CO LLP' FROM entities WHERE name='MASD & CO';
    """),
    (9, """
        -- Reclassify already-imported Debit Note vouchers from expense
        -- (textbook "purchase return" interpretation) to sales (this
        -- firm's "supplementary sales invoice" interpretation), and
        -- flip the sign on their splits from negative to positive so
        -- they ADD to partner revenue instead of subtracting from
        -- expenses.
        --
        -- v0.3.54 had Debit Note Registers landing in kind='expense'
        -- with line amounts negated (sign=-1). v0.3.56 treats them as
        -- revenue-positive; this migration brings any pre-v0.3.56
        -- already-imported DN data into the new shape so the operator
        -- doesn't have to clear + re-import to get a correct MIS.
        --
        -- Snapshot the targets to a TEMP table before mutating so the
        -- two UPDATEs don't see each other's effects. Idempotent: a
        -- second run finds zero rows because there are no more
        -- expense-side DNs after the first run.
        CREATE TEMP TABLE _dn_to_fix AS
            SELECT id FROM vouchers
             WHERE kind = 'expense'
               AND lower(vch_type) LIKE 'debit note%';

        UPDATE voucher_splits
           SET amount = -amount
         WHERE voucher_id IN (SELECT id FROM _dn_to_fix);

        UPDATE vouchers
           SET kind = 'sales'
         WHERE id IN (SELECT id FROM _dn_to_fix);

        DROP TABLE _dn_to_fix;
    """),
    (10, """
        -- Fixed office overhead per employee, set by management per
        -- month. Used in salary costing: each employee's monthly cost
        -- becomes (salary + this amount), distributed across the
        -- partner cost-centres via their timesheet hours. Settable
        -- per period since management can revise it month-to-month.
        CREATE TABLE IF NOT EXISTS fixed_office_overhead (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            period                TEXT NOT NULL UNIQUE,
            amount_per_employee   REAL NOT NULL DEFAULT 0,
            active                INTEGER NOT NULL DEFAULT 1,
            created_at            TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """),
    (11, """
        -- Per-row employee reimbursements (a separate sheet the operator
        -- uploads — distinct from the salary sheet's per-employee
        -- aggregate ``reimbursement`` column, which captures the
        -- monthly total). Each row says: "Employee X spent ``amount``
        -- for Client Y in this period; the client refunds us back
        -- iff client_reimbursable=1".
        --
        -- Cost-centre attribution: looked up from the CLIENT master at
        -- MIS-build time. Each row's cost lands on the partner who
        -- serves that client. When client_reimbursable=1 the
        -- corresponding revenue line comes through the Sales Register
        -- (as a 'Reimbursement' / 'OPE' ledger), so the partner P&L
        -- nets the wash naturally.
        CREATE TABLE IF NOT EXISTS reimbursements (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id              INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
            period                TEXT,
            txn_date              TEXT,
            employee_name         TEXT,
            employee_id           INTEGER REFERENCES employees(id),
            client_raw            TEXT,
            client_id             INTEGER REFERENCES clients(id),
            amount                REAL NOT NULL DEFAULT 0,
            client_reimbursable   INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_reimb_period ON reimbursements(period);
    """),
    (12, """
        -- Invoice number from the register's "New Ref" sub-row (the
        -- bill reference Tally records against the party ledger; for a
        -- purchase voucher it's the vendor's invoice number). Captured
        -- by the voucher-dump parser from the detailed register export;
        -- shown on the generated MIS's Expenses sheet next to the
        -- voucher number. NULL for vouchers imported from exports that
        -- don't include bill allocations.
        ALTER TABLE vouchers ADD COLUMN invoice_no TEXT;
    """),
    (13, """
        -- Canonicalise operator-typed financial years on the Targets
        -- master. Values like '2026 - 27' (spaces around the hyphen)
        -- never equalled the tight '2026-27' the MIS computes from the
        -- selected periods, so the Target column and the Budget-vs-Sales
        -- sheet silently read 0. Strip whitespace so stored values match.
        --
        -- Dedupe first (keep the highest id per CC + normalised FY) so
        -- the whitespace-strip can't trip the UNIQUE(financial_year,
        -- cost_centre_id) constraint when a clean row already exists.
        DELETE FROM targets
         WHERE id NOT IN (
           SELECT MAX(id) FROM targets
           GROUP BY REPLACE(financial_year, ' ', ''), cost_centre_id
         );
        UPDATE targets SET financial_year = REPLACE(financial_year, ' ', '');
    """),
    (14, """
        -- Provision costs (v0.3.82): a direct cost a partner cost centre
        -- EXPECTS to incur (tied to a client) but hasn't yet. Booked for a
        -- month; shown as a direct cost in the MIS and carried forward
        -- until adjustments bring the remaining to zero. Each adjustment
        -- records an actual amount incurred + the month it landed in.
        CREATE TABLE IF NOT EXISTS provisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            period      TEXT NOT NULL,
            entity_id   INTEGER REFERENCES entities(id),
            client_id   INTEGER REFERENCES clients(id),
            amount      REAL NOT NULL DEFAULT 0,
            note        TEXT,
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS provision_adjustments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            provision_id    INTEGER NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
            amount          REAL NOT NULL DEFAULT 0,
            adjusted_period TEXT,
            note            TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_prov_adj ON provision_adjustments(provision_id);
    """),
    # When you change the schema, append a new (version, sql) tuple here.
]


def latest_version() -> int:
    return MIGRATIONS[-1][0] if MIGRATIONS else 0


# --- Connection management ---------------------------------------------------

def connect() -> sqlite3.Connection:
    """Open a connection to the MIS database with sane pragmas applied.

    Performance pragmas tuned for the operator's workload (single-user
    desktop app, periodic bulk imports of 5k+ timesheet rows):

    * ``journal_mode = WAL`` — Write-Ahead Logging. Far faster than
      the default rollback journal for bulk inserts (no full-file
      rewrite per transaction). Survives crashes correctly.
    * ``synchronous = NORMAL`` — fsync only at WAL checkpoints, not
      every transaction. Safe under WAL; trades a tiny crash-window
      durability for 5-10× faster commit speed.
    * ``temp_store = MEMORY`` — keep sort/group/temp tables in RAM.
    * ``cache_size = -65536`` — 64MB page cache (negative = KB).

    Foreign-keys stays on. Both WAL settings are persistent on the
    DB file itself, so they only need to be set once, but re-setting
    each connection is cheap and protects against an external tool
    flipping them.
    """
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -65536")
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

    # Entity aliases — short forms + alternate names + location-only
    # tokens that appear in Tally letterheads. The matcher scans the
    # letterhead for any of these to pick the right entity when company
    # names collide (e.g. Bilimoria Mumbai and Bangalore share the
    # legal name; "Bengaluru" disambiguates).
    for alias, ent in [
        # Short forms.
        ("Bilimoria", "Bilimoria Mehta & Co."),
        ("Corporate", "Bilimoria Mehta Corporate"),
        ("Advisors", "MASD Advisors"),
        # Bangalore branch — distinguished from Mumbai by address tokens.
        ("Bengaluru", "Bilimoria Mehta & Co. (Bangalore)"),
        ("Bangalore", "Bilimoria Mehta & Co. (Bangalore)"),
        ("Jayanagar", "Bilimoria Mehta & Co. (Bangalore)"),
        # Tally's legal-name spellings for Corporate / MASD entities.
        ("BMC Corporate Solutions Pvt Ltd",
         "Bilimoria Mehta Corporate"),
        ("BMC Corporate Solutions", "Bilimoria Mehta Corporate"),
        ("BMC Corporate", "Bilimoria Mehta Corporate"),
        ("MASD ADVISORS PRIVATE LIMITED", "MASD Advisors"),
        ("MASD Advisors Private Limited", "MASD Advisors"),
        ("MASD & CO LLP", "MASD & CO"),
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

    # Manager seed. Each manager is bound to the partner cost-centre they
    # report under; the compound "MM - PP" code style mirrors how the firm
    # labels them in the master so the CC-string matcher can resolve names
    # like "Gaurav - Aakash" or "Sahil - Aakash" without ambiguity. A
    # manager can appear under multiple partners (Gaurav Siroya is under
    # both Aakash Mehta and Kiran Suvarna in the operator's setup) — each
    # role is a separate row keyed by the compound code.
    managers = [
        ("RM - PM", "Rajesh Malhotra",    "PM"),
        ("SR - AM", "Sahil Rathod",       "AM"),
        ("UV - AM", "Umesh Vishwakarma",  "AM"),
        ("GS - KS", "Gaurav Siroya",      "KS"),
        ("BS - SD", "Bhavya Shah",        "SD"),
        ("GS - AM", "Gaurav Siroya",      "AM"),
        ("BS - JV", "Bhavik Shah",        "JV"),
        ("KS - SD", "Kiwa Shah",          "SD"),
        ("HD - JV", "Hitesh Doshi",       "JV"),
        ("RR - VK", "Rutwick Ruparelia",  "VK"),
    ]
    for code, name, partner_code in managers:
        partner_row = conn.execute(
            "SELECT id FROM cost_centres WHERE code = ?",
            (partner_code,)).fetchone()
        cc_id = partner_row["id"] if partner_row else None
        conn.execute(
            "INSERT INTO managers(code, name, cost_centre_id) VALUES (?, ?, ?)",
            (code, name, cc_id))


if __name__ == "__main__":
    init_db()
    with transaction() as c:
        for tbl in ("entities", "cost_centres", "managers"):
            n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"{tbl}: {n} rows")
        v = c.execute("PRAGMA user_version").fetchone()[0]
        print(f"schema version: {v}")
