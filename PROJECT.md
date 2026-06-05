# Automated MIS Generator — Bilimoria Mehta & Co.

> Living document. Updated as we discuss. Last updated: 2026-05-29
>
> Current version: **v0.3.30** ([release history on GitHub](https://github.com/iodex99/bmc-mis-app/releases))

---

## 1. Purpose

An automated Management Information System (MIS) generator for the CA firm
**Bilimoria Mehta & Co.** and its associated entities. The operator (the firm's
accounts head) uploads exported files (Tally, timesheet, salary/reimbursement),
the system parses them, applies stored mappings, lets the operator review/edit,
and produces a **board-meeting-ready, formula-driven** MIS report.

Installed on the **accounts head's Windows computer**.

---

## 2. Core Entities (all must be flexible — add/edit/delete anytime)

### 2.1 Firms / Associated Entities
Each maintains its own Tally; reports are exported per entity.
1. Bilimoria Mehta & Co. (main)
2. Bilimoria Mehta Corporate
3. MASD & CO
4. MASD Advisors
5. Qualzen
6. Bilimoria Mehta & Co. (Bangalore)

### 2.2 Senior Partners = Cost Centres
1. Prakash Mehta (PM)
2. Kiran Suvarna (KS)
3. Jalpesh Vora (JV)
4. Aakash Mehta (AM)
5. Shreyans Dedhia (SD)
6. Vishal Kothari (VK)
7. Megha Mehta (MS)
8. Abhilash Lapasia (AL)

### 2.3 Managers (mapped to cost centres; promotable/demotable)
1. Rajesh Malhotra (RM)
2. Sahil Rathod (SR)
3. Umesh Vishwakarma (UV)
4. Gaurav Siroya (GS)

### 2.4 Employees / Team Members
- Hired under a partner; each employee maps to **(a) a Manager** and
  **(b) a Cost Centre**.
- Managers map to **a Cost Centre** only.
- Cross-client work: if an employee works on a client NOT belonging to their
  cost centre, that cost is attributed to the *concerned* cost centre.

---

## 3. Key Concept — "Senior Partner – Manager" String

Every Tally **voucher** (sales/expense entry) is mapped to a string of the form
`Senior Partner – Manager` (e.g. `PM – RM`). This gives full flexibility:
any voucher can be attributed to any partner/manager combination regardless of
the client's default cost centre.

### Voucher Splitting
A single client invoice may cover multiple services (audit, tax, etc.) worked
on by different cost centres. The operator can **split a voucher** into multiple
amounts, each split assigned its own `Senior Partner – Manager` string.

---

## 4. Inputs (uploaded files)

### 4.1 Tally Exports (per entity)
- Contains vouchers: sales and expenses.
- Each entry has: client/vendor, amount, cost centre (as recorded in Tally),
  a short description (e.g. "staff welfare"), and a **service** mapping.
- All entries map to a cost centre OR to "office expenses".
- **Format: TBD — see Open Questions.**

### 4.2 Timesheet
- Employees fill in hours worked per client.
- **Client name mismatch problem**: client name in timesheet ≠ client name in
  Tally (e.g. "XYZ Corporate" vs "XYZ Corporate Pvt Ltd"). Needs a
  matching/mapping mechanism.
- Timesheet does NOT tell us which manager/cost centre an employee belongs to —
  needs the employee→manager→cost-centre mapping.

### 4.3 Salary & Reimbursements Sheet
- Uploaded by operator monthly.
- Shows salary payments + reimbursements per employee.
- Added to the cost of the relevant cost centre.
- **Operator toggle**: include reimbursements in MIS or not.

### 4.4 Target Master
- Annual targets per cost centre (set per financial year).

---

## 5. Mapping / Memory Mechanisms (system "remembers forever", operator-editable)

| Mapping | Description | Future-proofing |
|---|---|---|
| Client → Cost Centre | From Tally entries | Cost centre can change; new clients prompt for mapping |
| Voucher → "Partner – Manager" string | Per voucher (splittable) | Editable before final MIS |
| Timesheet client → Tally client | Fuzzy name match, confirmed once | Re-mappable |
| Employee → Manager + Cost Centre | Confirmed once | Re-mappable; new employees prompt |
| Manager → Cost Centre | Confirmed once | Re-mappable; promotion to partner supported |
| Service → (used for service-based MIS) | From Tally | — |

- On first import, the system asks the operator to confirm matches.
- Whenever a new/unknown client or employee appears in any file, the system
  prompts the operator to map it before proceeding.
- All mappings editable by operator before generating the final MIS.

---

## 6. Calculations

### 6.1 Hourly Rate / Cross-Client Costing
- Employee's monthly pay ÷ hours worked = effective hourly rate.
- Combined with timesheet (hours per client), allocate labour cost to each
  client — including cross-client work — and roll up to cost centres.

### 6.2 Cost Centre P&L
- Revenue (sales vouchers) − direct costs (expense vouchers) − labour
  (salary allocation) ± reimbursements = cost centre profitability.
- Compared against the annual target.

---

## 7. MIS Output Requirements

- **Board-meeting-ready**, polished, error-free.
- Cells **formula-driven** wherever possible (not hard-coded numbers).
- Multiple views: by entity, by cost centre, by `Partner–Manager`, by service.
- **Historical data stored** — compare any prior period vs current period;
  operator chooses the reporting period.
- Historical storage must be "smart" — data flows gracefully into any
  calculation/comparison across periods.

---

## 8. Open Questions (awaiting answers — see conversation)

### Resolved — see Decisions Log
Tech stack, Tally format, output format, office expenses, financial year,
hourly-rate basis, MIS views, partner remuneration.

### Still needed before building
1. **Sample files** (most important): a real Tally export (.xlsx), a timesheet
   file, and a salary & reimbursements sheet — so parsers match real columns.
2. Exact MIS report layout / sections the board expects (or approve a draft
   layout I propose).
3. Whether the four entity Tallies use one consistent export layout or differ.
4. How a period is defined for upload — one Tally file per entity per month?

---

## 9. Decisions Log

- **2026-05-22** — Tech stack: **Python desktop app** (GUI + local SQLite DB,
  generates Excel reports).
- **2026-05-22** — Tally export format: **Excel (.xlsx/.xls)**.
- **2026-05-22** — Final MIS output: **Excel workbook** (multi-sheet,
  formula-driven).
- **2026-05-22** — Office/shared expenses: **operator chooses per report**
  (toggle: allocate to cost centres vs. show separately).
- **2026-05-22** — Financial year: **April–March** (Indian standard).
- **2026-05-22** — Hourly rate basis: **total timesheet hours** logged by the
  employee that month (across all clients).
- **2026-05-22** — MIS includes **all four views**: Cost Centre P&L,
  Partner–Manager P&L, Entity-wise P&L, Service-wise MIS.
- **2026-05-22** — Partner remuneration/drawings are **NOT** a cost; cost
  centre profit is the partner's earning.
- **2026-05-22** — Reporting period = **calendar month** for vouchers
  (sales / purchase) and salary; every row is bucketed by its actual
  date regardless of the file's label.
- **2026-05-29** (v0.3.18) — **Timesheet uses the firm's 21st → 20th
  cycle** instead of calendar month. A timesheet row from 25 Dec
  contributes to **Jan MIS** (because the firm's Jan timesheet window
  is 21 Dec → 20 Jan). Hourly-rate labour allocation in Jan MIS uses
  Jan salary ÷ (21 Dec → 20 Jan hours).
- **2026-05-22** — Managers: only the 4 named managers are treated as managers
  for now; system stays flexible (timesheet "Reporting Manager" stored as-is,
  not all 28 names need mapping).
- **2026-05-22** — Non-billable / internal timesheet time → **firm overhead**
  (subject to the office-expense allocation toggle).
- **2026-05-22** — Salary sheet's `Cost centre` column is the **source of
  truth** for salary cost; system flags only unknown/blank values.
- **2026-05-22** — `PG` cost centre: ignore. `Office` = firm-overhead bucket.
- **2026-05-22** — File layouts differ across entities/sheets → parser uses a
  **flexible import-template engine** (operator maps columns once per new
  layout; template saved & auto-reused).

---

## 10. Architecture / Build Notes

**Stack:** Python 3.12 · PySide6 (Qt GUI) · SQLite · openpyxl · rapidfuzz.

**Layout:**
- `app/config.py` — paths & shared constants.
- `app/database.py` — schema, connection, first-run seeding.
- `app/repository.py` — generic CRUD helpers.
- `app/ui/` — Qt pages (`main_window`, `master_data`, `style`, …).
- `app/main.py` — entry point (`python -m app.main`).
- `data/mis.db` — SQLite DB (override location via `BMC_MIS_DATA` env var).

**Build progress:**
- ✅ Phase 1 — skeleton, schema, seed data (6 entities, 9 cost centres incl.
  Office, 4 managers).
- ✅ Phase 2 — Master Data page: tabbed CRUD for all 7 master tables, soft
  delete, FK dropdowns.
- ✅ Phase 3 — import engine: `app/importing/` (excel_reader, fields,
  valueutils, models, parsers, templates, commit) + Import Files page with
  column-mapping dialog. Tested against all 3 sample files — purchase (57
  vouchers), timesheet (4,252 rows), salary (180 rows) parse & commit cleanly.
- ✅ Phase 4 — Review & Map: client/employee fuzzy resolution with alias
  memory, bulk-create escape hatch, voucher split editor (Partner–Manager +
  service per split).
- ✅ Phase 5 — calculation engine (`app/services/calc.py`): revenue/expense/
  labour facts, hourly-rate labour allocation, cost-centre/Partner-Manager/
  entity/service roll-ups, overhead allocation modes, pro-rated targets.
- ✅ Phase 6 — MIS workbook generator (`app/services/report.py`) + Generate
  page: formula-driven Excel (Cover, Dashboard, Cost Centre P&L,
  Partner-Manager P&L, Entity P&L, Service MIS, data sheets). Verified with
  the `formulas` engine that workbook totals match the calc engine.

- ✅ Phase 7 — historical comparison: Generate page offers an optional
  comparison period; workbook gains a Comparatives sheet (current vs prior,
  revenue & profit Δ) with its own live data sheets.
- ✅ Phase 8 — packaging: `run.py` entry point, `build.py` (PyInstaller),
  `installer.iss` (Inno Setup), `README.md`. Packaged app stores data under
  `%LOCALAPPDATA%\BMC MIS`. Dashboard page added (status + next steps).

**Labour-costing rule (decided during build):** the salary sheet provides the
*amount* (an employee's monthly pay); the timesheet provides the *allocation*
(pay spread over clients worked, hourly rate = pay ÷ total hours). Non-billable
/ unmapped client hours → Office. No timesheet hours → salary-sheet cost centre.

**Status: all 8 phases complete.** App runs via `python run.py`; build the
Windows .exe with `python build.py`.

---

## 16. Post-launch iterations (v0.2.0 → v0.3.30)

Released privately to GitHub (`iodex99/bmc-mis-app`) and updated on the
operator's PC via the in-app updater. Highlights of every release in order:

### v0.2.0 — In-app updater pipeline
- `app/services/updater.py` checks GitHub Releases (using an embedded
  fine-grained PAT) and downloads + applies updates in place.
- Settings page added with version info, "Check for updates", auto-check
  toggle, and a status-bar pill for available updates.
- Schema migration runner (`MIGRATIONS = [(version, sql), …]` in
  `database.py`) so future schema changes apply cleanly to installed copies.
- GitHub Actions workflow (`.github/workflows/release.yml`) auto-builds the
  `.exe` on every `vX.Y.Z` tag push.

### v0.3.0 — Sales Register support + service-wise MIS
- `.xls` reading via `xlrd` (Tally exports Sales Register in legacy format).
- New **flat-row sales parser** (separate from the voucher-block parser used
  for purchase) — one voucher per invoice row.
- Column-mapping dialog gains a **per-column role** section: each column is
  marked **Ignore / Service / Tax**. Service columns become revenue splits;
  tax/TDS/round-off columns are summed into the tax total.
- New master table `cc_string_mappings` (schema v3): the raw Tally
  "Cost Center" string ("Mr. Shreyans Dedhia", "Prashant - Shreyans", etc.)
  → (partner cost-centre, manager).
- New Review tab **Cost Centres** with the same fuzzy-suggest + map flow.
- ResolveCcStringDialog includes inline "+ New manager" creation for
  managers not in the master yet.
- Cancelled invoices (`(cancelled)` cost-centre) are skipped at import.

### v0.3.1 → v0.3.6 — Plumbing for the updater
- Indian number format (`fmt_inr`) used throughout UI + workbook.
- Post-import prompt: "X unmapped clients / Y employees / Z cc-strings —
  Resolve now / Later" with one-click navigation to Review.
- Updater fixes:
  - Background-thread workers were getting GC'd before the signal fired —
    hold `self._worker` references explicitly.
  - GitHub `/releases/latest` returns 404 when nothing is flagged "latest";
    fall back to listing `/releases` and picking the highest semver.
  - PAT permissions matter — fine-grained with `Contents: read-only` works.

### v0.3.7 → v0.3.10 — UI scrollability + headless updater
- Column Mapping dialog wrapped in a `QScrollArea` so OK/Cancel never fall
  off the screen.
- `NoScrollComboBox` / `NoScrollSpinBox` (in `app/ui/widgets.py`) so the
  mouse wheel scrolls the dialog instead of changing dropdown values.
- Update helper hardened: `CREATE_NO_WINDOW` flag (no visible cmd window),
  PID-based wait (more reliable than image name), 5s post-PID sleep so DLL
  handles release, `update.log` written into the install folder so failures
  are debuggable, temp-folder cleanup removed (was hanging on the bat's
  own working dir).

### v0.3.12 — Whitespace-insensitive name matching
- Client → voucher matching now uses Python `norm()` (collapses runs of
  whitespace) instead of SQL `LOWER(TRIM(…))`. Without this the operator
  would map "Daftary -Descon Engineering Private  Limited" (two spaces) and
  it'd never link to the voucher row because SQL TRIM keeps the double
  space. Same fix already in place for cc_string mappings.
- Voucher Split Editor combos / amount spinbox use NoScroll variants.

### v0.3.13 — UX overhaul
- **Inline row action buttons** on every Review and Master Data table:
  `Resolve →` / `Edit` (indigo primary) and `Deactivate` / `Delete`
  (light red). No more "double-click a row to do anything".
- **Status pills** per row: yellow "Unmapped", green "Active", grey
  "Inactive", red "Needs fix".
- **Tab badges** show unresolved / active counts: "Clients (4)",
  "Cost Centres (3)", "Vouchers (12)".
- **Dashboard welcome state**: when there's no data, a friendly
  gradient panel with one-click jumps to Import or Master Data.
- **Dashboard metric cards** (revenue / costs / profit / items to
  review) with accent-bordered tiles + quick-action cards that emit a
  `navigate` signal to jump to the relevant page.
- Empty states: "✓ Every client name is mapped" instead of empty tables.
- Stylesheet polish: hover effects on quick cards, accent borders on
  metric tiles, status pill colors, danger-zone styling.

### v0.3.14 — Sales-Register-aware client cost-centre inference
- `infer_client_cost_centres()`: walks every client without a
  `cost_centre_id` and sets it to the dominant cost centre seen on its
  sales voucher splits.
- `suggest_cc_for_raw_client(raw)`: looks up the dominant cost centre for
  a raw client name. Used to pre-fill the **Resolve Client** dialog's
  cost-centre dropdown with a green "✓ inferred from Sales Register"
  confirmation banner.
- Inference runs at end of import commit, in `apply_known_client_aliases`,
  in `link_client` / `create_client` / `bulk_create_clients`, and after
  `map_cc_string`.

### v0.3.30 — Handle malformed XML from real Tally
The first live Tally pull from BMC Corporate raised
``reference to invalid character number: line 209, column 23`` —
Tally's XML payload contained illegal control-byte references (``&#1;``,
``&#11;``, ``&#x1B;`` etc.) embedded in ledger / cost-centre strings.
Python's expat parser refuses XML 1.0 control characters. We now strip
them before parsing.

- **`_sanitize_xml_bytes`** in `tally_xml.py` drops:
  - raw control bytes ``\x00-\x08``, ``\x0B``, ``\x0C``, ``\x0E-\x1F``
  - decimal references ``&#0;`` to ``&#8;``, ``&#11;``, ``&#12;``,
    ``&#14;`` to ``&#31;``
  - hex references ``&#x0;`` to ``&#x8;``, ``&#xB;``, ``&#xC;``,
    ``&#xE;`` to ``&#x1F;``
  - leading UTF-8 BOM
- **CP1252 fallback** in `_parse_xml`: if UTF-8 decode fails (Tally ERP 9
  in non-Unicode mode), retry as Windows-1252.
- **Debug dump**: any future parse failure now writes the raw response to
  ``<data dir>/tally_debug_<timestamp>.xml`` and surfaces the path in
  the operator's error dialog, so we can reproduce the issue offline.
- **Unit-tested** against 5 problematic input shapes: clean, decimal
  refs, hex refs, raw control bytes, cp1252 payload — all parse cleanly
  and yield the right voucher + CC data; vanilla `ET.fromstring` fails
  on cases 2-5 without the fix.

### v0.3.29 — Fix calendar popup truncating day numbers
On Windows + Fusion style, the QDateEdit calendar popup was rendering
two-digit day numbers as ``...`` because its columns squeezed below the
text width. Forcing a 340x260 minimum size on the underlying
QCalendarWidget (plus a stylesheet that gives each cell breathing room
and matches the app's indigo / navy palette) makes every day fully
readable in both From and To pickers on the Pull-from-Tally section.

### v0.3.28 — Pull data directly from Tally (primary workflow)
The MIS app now talks to Tally's built-in HTTP/XML gateway on the same
machine. Operator opens a company in Tally, picks a date range in the
MIS app, hits one button — vouchers flow in with full per-line cost
centre attribution. No paid API, no internet, nothing leaves the PC.
Excel upload stays as a graceful fallback.

- **New `app/importing/tally_xml.py`** — parses Tally's Day Book XML
  response into the same `ParsedVoucher` / `VoucherLine` dataclasses the
  Excel parser produces. Commit / dedup / CC auto-match / MIS generation
  all operate identically downstream — only the transport changed.
- **New `app/importing/tally_client.py`** — HTTP POST to the gateway
  with envelope builders for:
  - `current_company()` — which company is loaded right now (used for
    the connection probe + auto-routing to the right MIS entity)
  - `list_companies()` — every company Tally has loaded
  - `fetch_day_book(from, to)` — every sales + purchase voucher in the
    range, with exploded ledger + CC sub-rows
  All requests go to a single configurable URL (default
  `http://localhost:9000`). Connection / timeout / HTTP-error cases each
  raise a `TallyError` with an operator-friendly message including the
  exact setup steps for the Tally Connectivity panel.
- **New `app/ui/tally_pull.py`** — a `TallyPullWidget` that hosts at
  the top of the Import Files page. URL field with a Test button, date
  range pickers, entity-mapping dropdown ("Auto-detect from Tally" by
  default — matches the loaded company against the entity master /
  aliases), and a single Pull button. Background `QThread` workers so
  the UI doesn't freeze during a fetch. Result panel shows new /
  duplicate / amount-mismatch counts per kind.
- **Excel upload section** moved below as "Fallback: upload an Excel
  file". Same controls, same flow, used when Tally is closed / on a
  different machine / for a one-off historical import. The whole page
  scrolls so both sections fit.
- **Settings page** gained a Tally connection section — Tally URL
  field + Save button that pings the URL after writing and reports
  reachability. Persisted in `app_settings(key='tally_url')`.
- **Auto-entity-matching on pull** — when the operator chooses
  "Auto-detect from Tally", the widget asks Tally for the currently-
  loaded company and looks it up in the entity master via the existing
  `entity_aliases` table (so "Bilimoria" matches "Bilimoria Mehta & Co.").
  Falls back to the dropdown when nothing matches.
- **Dedup behaviour unchanged** — re-pulling the same period skips
  every voucher whose `(entity_id, kind, vch_no)` already exists, with
  amount mismatches surfaced separately. Built-in idempotency for the
  workflow "operator re-runs mid-month after a Tally edit".
- **End-to-end verified** with a mock Tally HTTP server: connection
  probe, current-company + list-companies discovery, Day Book pull
  with 4 vouchers (2 sales — including a multi-partner-per-voucher
  case — and 2 purchases), per-line CC attribution preserved through
  XML, commit, auto-match, MIS workbook generation, dedup on re-pull,
  and error paths (bad URL, reversed date range).

### v0.3.27 — Clean number format for small values
The previous Indian-grouping format string was over-provisioned for
crore-level values — it had escaped commas (``\,``) all the way out to
10,000 crore in both positive and negative sections. Escaped commas in
Excel format strings are **literal**: they render even when the preceding
``#`` placeholder has no digit to fill. Result: a cell holding ``1,500``
could pick up phantom commas on screen, and the format string shown in
Excel's cell-format dialog looked ugly even for hundreds/thousands cells.

- **New three-tier `INR` format** in `app/services/report.py`:
  - ≥ 1 crore → ``1,23,45,678`` (full lakh-crore grouping)
  - ≥ 1 lakh, < 1 crore → ``1,23,456`` (lakh grouping)
  - < 1 lakh → ``1,500`` (standard 3-digit grouping)
- Excel allows only 3 conditional numeric sections, so big-negative red
  styling was dropped in favour of clean small-number rendering — most MIS
  values are positive and negatives are usually small variance numbers.
  Negatives render with a regular minus sign.
- Applies to every money cell across Cover, Dashboard, Cost Centre P&L,
  Partner-Manager P&L, Entity P&L, Service MIS, Budget vs Monthly Sales,
  Comparatives, and the Revenue / Expenses / Labour data sheets.

### v0.3.26 — Smart Tally voucher-dump parser + dedup
The user's "actual" Tally export — multi-row voucher blocks with indented
Dr/Cr cost-centre sub-rows — is now the primary supported format. Goal: zero
manual column mapping, per-line cost-centre attribution, idempotent
re-uploads. Verified against the four sample files (BMCA sale, Corporate
sale, BMCA purchase, Corporate purchase).

- **Header sniffer** (`app/importing/sniffer.py`). Scans the first ~30 rows
  for a Tally-style header (Date + Particulars + Vch No + Debit + Credit;
  synonyms tolerated — "Vch No.", "Voucher No.", "Vch Num", etc.). Returns
  the column map auto-derived from the header text — column positions can
  differ entity-to-entity. Also detects "Sales Register" / "Purchase
  Register" banner and overrides the file-type dropdown if the operator
  picked the wrong one. Import UI bypasses the column-mapping dialog
  entirely when the sniffer succeeds.
- **`parse_tally` rewritten** for per-line splits. Each ledger row inside a
  voucher block becomes its own `VoucherLine` (service + cost-centre +
  amount + is_tax flag). Multi-service vouchers where audit goes to one
  partner and certification goes to another now split correctly — the
  previous version aggregated to a single "dominant" CC per voucher.
- **`VoucherLine` dataclass** added to `app/importing/models.py`; populated
  by the voucher-dump parser via the new `ParsedVoucher.line_splits` list.
- **Per-split cost-centre string.** New `voucher_splits.raw_cost_centre`
  column (migration v5) — each split carries its own Tally CC string so
  multi-CC vouchers stay attributed line-by-line. Existing splits are
  back-filled from their parent voucher's `raw_cost_centre`.
- **`apply_known_cc_string_mappings`** now updates each split using the
  split's own `raw_cost_centre` (falling back to the parent voucher's for
  legacy data). `unresolved_cc_strings` and `delete_unmapped_cc_string_rows`
  follow the same pattern.
- **Dedup on re-import.** Vouchers carry a natural key of `(entity_id,
  kind, vch_no)`. On commit, vouchers with a matching key are skipped;
  amount mismatches are recorded and surfaced in the post-import dialog.
  New `CommitReport` dataclass replaces the bare `batch_id` return so the
  UI can show a per-batch breakdown ("19 new, 0 duplicates, 0 mismatches").
  Migration v5 adds an index on `(entity_id, kind, vch_no)` for the lookup.
- **GST / TDS rows** are detected by keyword (`is_tax_head`) and rolled
  into `voucher.tax_amount` instead of becoming splits — keeps partner
  revenue numbers clean.
- **Service auto-create** unchanged but now exercised by the new parser —
  unrecognised ledger names ("Certification", "Audit & Assurance", etc.)
  get inserted into the services master on first sight.
- **Verified results** against the real files:
  - BMCA sale: 19 vouchers, splits attributed to VK / JV / SD / AM by the
    existing fuzzy CC matcher (including the partner-manager string
    "Gaurav S -Aakash" → AM).
  - Corporate sale: 31 parsed → 30 inserted + 1 intra-file dedup
    ("CSM/26-27/74" appears twice in the source); per-line CC splits like
    "Shreyans-Bhavya" resolve to (SD, Bhavya-as-manager) correctly.
  - Purchase BMCA / Corporate: Staff Welfare / Professional Charges
    attributed to `Office` cost centre.
  - Re-importing the same file: 19 new on first pass, 0 new + 19 skipped
    on the second.
  - Modifying one voucher's gross amount and re-uploading: 18 skipped +
    1 flagged as an amount mismatch with the prior gross + new gross.

### v0.3.25 — Budget vs Monthly Sales sheet; Net Profit on the matrix
Picking up where v0.3.24 left off — three more pieces lifted from the firm's
reference workbook layout:

- **New "Budget vs Monthly Sales" sheet** (between Dashboard and Cost Centre
  P&L). Layout mirrors their "Budget and P&L" top block:
  - One row per partner cost centre, one column per FY month from April
    through the latest selected period (so a January MIS shows Apr–Jan).
  - "Annual Budget" column reads from the Targets master for the relevant
    Indian FY (e.g. `2025-26`).
  - Monthly cells are values queried directly from the database — they show
    the full FY-to-date picture regardless of which periods the operator
    selected for the main MIS (so the board still sees prior-month context
    on a single-month run).
  - "YTD Total", "Variance vs Budget", "Avg / Active Month" are formula-
    driven (`SUM`, `COUNTIF`), so editing a monthly value recalculates.
  - Total row at the bottom; freeze panes after the Budget column.
- **Office Overhead, Net Profit, Net Profit % rows added to the Partner-
  Manager P&L matrix.** Office overhead is partner-level (allocated by the
  calc engine's overhead-mode), so manager columns stay blank and only the
  Total column carries the value. Net Profit = Gross − Overhead; Net Profit
  % is recomputed (not summed) at every Total / MIS Total cell.
- **Wired into `generate()`** in the right order: Cover → Dashboard →
  Budget vs Monthly Sales → Cost Centre P&L → Partner-Manager P&L → …
- Smoke-tested with synthetic data: all formulas render as valid Excel
  expressions; per-cell values match expectations (manager columns = 0
  on overhead/net rows, Total columns carry the values, MIS Total sums
  across partner Totals for amounts and recomputes ratios for percentages).

### v0.3.24 — Bilimoria-style Partner-Manager P&L matrix
Reference: the firm's actual MIS workbook (Apr'25 → Jan'26) — the
Partner-Manager P&L there uses a matrix layout where each partner is
a merged super-header spanning their manager sub-columns, with a
"Total" column per partner and a final "MIS Total" column on the right.
Every cell is `SUMIFS` over flat data sheets. Replicated and enhanced:

- **Replaced** the flat "Partner-Manager P&L" sheet with a matrix:
  - Row 4: Partner names, merged across each partner's manager block.
  - Row 5: Manager codes ("Self" column uses the partner's own code) +
    "Total" per partner.
  - Final column: "MIS Total" summing across all partners.
- **New P&L rows** matching the firm's standard:
  - Sales (Income) — `SUMIFS` filtered by Category = "Income"
  - Reimbursement & OPE — `SUMIFS` filtered by Category IN ("Reimbursement",
    "OPE")
  - **Total Income** (bold, highlight) — `=Sales + Reimb`
  - Salary (labour cost — partner-level, in the "Self" column only)
  - Other Direct Expenses
  - **Total Direct Costs** (bold) — `=Salary + Other`
  - **Gross Profit** (bold) — `=Total Income − Total Direct Costs`
  - **Gross Profit %** — `=Gross / Total Income`, with proper
    per-partner-total ratio recomputation (not a sum of percentages).
- **Service category detection** added to the Revenue data sheet:
  service names matching "reimbur" → Reimbursement; "out of pocket" / 
  "ope" → OPE; "round off" → Other; else → Income. The Category becomes
  column H on the Revenue sheet, used by the SUMIFS in the P&L.
- Tested against the real samples — sheet builds cleanly, formulas are
  valid Excel SUMIFS / SUM / IF expressions, matrix scales to however
  many manager combinations exist in the data.

### v0.3.23 — Richer Generate-MIS preview (primary + comparison)
- The "Preview totals" button on the Generate MIS page now shows:
  - The actual period(s) being included
  - Revenue (+ number of revenue entries / splits)
  - Cost (+ split between expense and labour)
  - Net profit
  - Cost centres with activity
- When a comparison period is also selected, the same block is shown
  for the comparison run beneath the primary, so the operator can
  sanity-check that the right data is being pulled before exporting.
- No calc engine changes — period filtering was already correct
  (`period IN (selected periods)` for vouchers / salary / timesheet).

### v0.3.22 — Filters & search across Review and Master Data; header sort
- **Voucher Entity dropdown bug fix.** The combo was showing integer ids
  ("1", "6", "2"…) instead of entity names because the `(label, data)`
  iteration was inverted against what `repo.fk_options()` returns. The
  filter was also broken — selecting "1" sent the entity *name* into the
  WHERE clause, so it never matched. Both fixed.
- **New Status filter** on the Vouchers tab: All / ⚠ Needs fix only /
  ✓ OK only.
- **New search box** on the Vouchers tab: matches party, client or
  voucher no. Debounced 200 ms so it doesn't refilter on every keystroke.
- **Search boxes** added to Review → Clients, Employees, Cost Centres
  (debounced; counts show "X of Y matches…" when filtering).
- **Search box** added to every Master Data tab (Entities, Cost Centres,
  Managers, Employees, Clients, Services, Annual Targets); matches any
  field on each row.
- **Header-click sorting** enabled on every table via
  `setSortingEnabled(True)` in `setup_data_table`. Default sort by
  display text — fine for names and dates, less precise for numeric
  columns (good-enough for now).
- New helper `widgets.debounced(callback, ms=250)` shared by all the
  search inputs so we don't duplicate timer plumbing.

### v0.3.21 — Smart auto-matching of Tally Cost-Centre strings
- New `resolution.auto_match_cc_strings()` does fuzzy matching to find
  the right partner (and manager) for each raw Cost-Centre string:
  - **Strips honorifics** ("Mr.", "Ms.", "Mrs.", "Dr.", "Shri", "Smt").
  - **Normalises whitespace** (handles Tally's stray double-spaces).
  - **Splits on hyphen / dash** to try "Manager - Partner" or
    "Partner - Manager" orderings; picks the side that maps to a
    partner; only attaches a manager if its match score ≥ 80%.
  - **Two scorers**: token-sort-ratio + partial-ratio, takes the
    higher — so "Shreyans" matches "Shreyans Dedhia" (partial), and
    "Jalpesh  Vora" with double space matches "Jalpesh Vora"
    (token-sort).
- Runs **automatically at import commit** (right after applying saved
  cc-string mappings), so most cc strings resolve themselves on first
  import. The remaining few (manager-only strings, genuinely ambiguous)
  still need operator input.
- Also runs on Review page open, so the Voucher tab's "needs fix"
  count drops as soon as you navigate there.
- Cost Centres tab's "⚡ Re-apply known" button replaced by
  "⚡ **Auto-match all**" (primary indigo) which runs both passes.
- Verified against the firm's 11 sample cc strings: **10/11
  auto-resolved correctly** (the 11th, "Rajesh Malhotra", is a
  manager-only string with no partner indicator — needs manual input).

### v0.3.20 — Hotfix: missing QPushButton import
- v0.3.19 added the "Load all N row(s)" pagination button to the Salary
  and Timesheet tabs but I forgot to import `QPushButton`. The app
  crashed at launch with `NameError: name 'QPushButton' is not defined`.
  One-line fix; no behaviour change.

### v0.3.19 — Records page performance: doesn't freeze on big data
- Five separate fixes to `fill_table_with_actions` and the Records tabs:
  1. **Lazy load** — `RecordsPage.showEvent` only refreshes the active
     tab. Was loading all three on every nav-click, so even visiting
     Records re-built the 4k-row timesheet table.
  2. **Interactive resize mode** — was using
     `QHeaderView.ResizeToContents` which scans every cell to compute
     column widths. At ~4 k rows × 7 columns this was a multi-second
     freeze. Now uses Interactive widths based on header-text length,
     with one column getting Stretch. User can still drag column edges.
  3. **Uniform row height via `verticalHeader().setDefaultSectionSize`**
     — single call instead of N `setRowHeight(r, …)` calls.
  4. **Batched updates** — wrap the cell-population loop in
     `setUpdatesEnabled(False)` / `setSortingEnabled(False)` so Qt
     doesn't repaint and re-sort after every cell.
  5. **Soft pagination** — `_PAGE_LIMIT = 2000`. Above that, the table
     shows the first 2 k rows and a "<i>(showing first 2,000)</i>" hint
     + a "Load all N row(s)" button below the table. Totals (count,
     sum) always reflect the full dataset.
- **Default to the latest period** instead of "(all periods)" so a
  freshly-opened Salary / Timesheet tab loads one month, not all months.
- `list_salary` and `list_timesheet` gain a `limit` parameter.

Benchmarks (offscreen, simulated): 4 252 timesheet rows fill in
**~100 ms** (was multi-second); 2 000 rows in **~48 ms**.

### v0.3.18 — Timesheet uses the firm's 21st → 20th cycle
- Reverses the v1 "all data is calendar-month" decision **for timesheet
  only**. The firm's reality:
  - Salary: calendar month (1 Jan → 31 Jan goes under period `2026-01`).
  - Timesheet: 21st of previous month → 20th of current month (so a row
    from 25 Dec contributes to **Jan MIS**, not Dec MIS).
- New helper `valueutils.mis_period_for_timesheet_date(date)` —
  day ≤ 20 → current month, day ≥ 21 → next month.
- `parse_timesheet` now uses it instead of `period_of(date)`.
- **Migration v4** re-buckets every already-imported timesheet row to
  its correct MIS month via SQL — runs once when the operator updates.
- Records → Timesheet now shows the convention in its intro text so the
  operator isn't confused when 25-Dec rows appear under `2026-01`.
- Vouchers (sales / purchase) and salary still use calendar months.

### v0.3.17 — Delete unmapped rows + multi-select on Review tabs
- Every Review tab (Clients, Employees, Cost Centres) now has a per-row
  **Delete** button in the Actions column (red, secondary) next to
  **Resolve →**. Deleting an unmapped name permanently removes the
  underlying sales-voucher / timesheet / salary rows associated with
  that raw name. Strongly worded confirmation; no undo.
- Tables switched from single-select to **extended-select** (Ctrl+click,
  Shift+click). A "🗑 Delete selected (N)" button appears in the top
  toolbar and is disabled until at least one row is picked.
- Resolution service gains `delete_unmapped_client_rows()`,
  `delete_unmapped_employee_rows()`, `delete_unmapped_cc_string_rows()`
  — all whitespace-insensitive, all use Python-side `norm()` matching.
- `voucher_splits` cascades on `vouchers` delete (existing FK), so cleanup
  is automatic.

### v0.3.16 — Records page (browse stored data, delete an import)
- New top-level nav **Records** (between Review & Map and Master Data)
  with three tabs:
  - **Import batches** — every file ever imported, newest first, with
    row counts and a per-row **Delete** action (cascades to vouchers /
    timesheet / salary rows; preserves saved column-mapping templates
    and the master records you mapped from those rows).
  - **Salary** — every salary row across every period; filter by period
    + employee name; running totals (rows, employees, ₹ salary,
    ₹ reimbursement).
  - **Timesheet** — every line across every period; filter by period +
    employee + client; running totals (rows, employees, clients, hours,
    billable hours).
- New service module `app/services/records.py` for the underlying
  queries; UI in `app/ui/records_page.py`.
- Closes the previously-invisible UX gap: salary & timesheet rows were
  being stored period-tagged in `salary_entries` / `timesheet_entries`,
  but there was no way to verify what was loaded short of generating an
  MIS workbook. Operator can now see every row, filter by month, and
  undo a wrong import without nuking everything via Clear All Data.

### v0.3.15 — Auto-inference for everything + Clear All Data
- Auto-inference extended to **every link the system can derive**:
  - `infer_employee_cost_centres()` — Salary sheet `cost centre` →
    `employees.default_cost_centre_id`.
  - `infer_employee_managers()` — Timesheet `Reporting Manager` →
    `employees.manager_id` (only when that name fuzzy-matches a manager
    already in the master).
  - `infer_manager_cost_centres()` — dominant cost centre of an
    manager's employees → `managers.cost_centre_id`.
  - `infer_client_cost_centres()` — as in v0.3.14.
- Umbrella function **`infer_all_masters()`** runs all four passes;
  called after import commit, every resolve dialog, every bulk-create
  and every cc-string mapping save.
- All inference is whitespace-insensitive (via `norm()`), idempotent,
  and **never overwrites operator-set values**.
- New module **`app/services/reset.py`** — `reset_all_data()` deletes
  every row from every user table (foreign-keys-off so order doesn't
  matter), resets `sqlite_sequence`, then re-runs `_seed()` to restore
  firm defaults.
- New **Danger Zone** section in Settings:
  - **Clear all data…** — two-step confirmation (warning + type
    `RESET`), then wipe + relaunch prompt.
  - **Open data folder** — opens `%LOCALAPPDATA%\BMC MIS\` in Explorer.
- Stylesheet adds `QGroupBox#dangerZone` styling (red border, light red
  background, red title).

---

## 17. Operator's data location

| What | Path on the installed PC |
|---|---|
| Database (everything the app knows) | `%LOCALAPPDATA%\BMC MIS\mis.db` |
| Generated MIS workbooks | `%LOCALAPPDATA%\BMC MIS\exports\` |
| Update helper log (when applicable) | `<install folder>\update.log` |

The data folder is **completely separate from the install folder**, so the
auto-updater never touches it. Backup = close the app, copy `mis.db`.

---

## 18. Workflow for shipping an update

From the dev PC:

1. Make code changes.
2. Bump `__version__` in `app/__init__.py`.
3. `git commit -am "..." && git push`.
4. `git tag vX.Y.Z && git push origin vX.Y.Z`.

GitHub Actions takes over: builds the `.exe` (embedding the
`UPDATER_TOKEN` PAT from repo secrets), zips the output, attaches it to a
new Release with `make_latest: true`. Within a minute or two the installed
copy's silent auto-check on launch picks it up; the operator clicks the
pill in the status bar → Install update → app restarts on the new version
hands-off.

**Verified parser behaviour (sample files):**
- Purchase register: voucher blocks detected, GST/TDS/round-off separated into
  `tax_amount`, net = taxable value. Cost-centre allocation rows captured.
- Timesheet: `HH:MM` durations → hours; "Non Billable" flagged.
- Salary: 179/180 cost centres auto-resolved (1 = ignored `PG`).

---

## 11. Sample File Analysis (2026-05-22)

Three sample files were provided and inspected.

### 11.1 `Bilimoria Mehta & Co. Purchase Register - Mumbai 2.xlsx`
- Single sheet `Purchase Register`. Rows 0–5 = firm name/address/title/period
  (`1-Jan-26 to 31-Jan-26`). Row 7 = headers. Data from row 8.
- Headers: `Date | Particulars | (blank) | (blank) | Vch Type | Vch No. |
  Debit | Credit | Taxable Amount`.
- **Each voucher is a multi-row block:**
  - Row 1 of block: Date, Party/vendor name, Vch Type, Vch No., Credit total,
    Taxable Amount.
  - Following rows: ledger heads (e.g. "Staff Welfare", "Office Rent",
    "Input CGST", "TDS 94C", "ROUND OFF") with the Debit amount.
  - Under each ledger head, a row with the **cost centre** in Particulars
    (here always `Office`) + amount + `Dr`.
- ⚠️ This register has **no service column** and the cost centre is always
  `Office` → these are firm overhead expenses, not partner-attributed.
- ⚠️ Tax lines (Input CGST/SGST, TDS, ROUND OFF) must be separated from the
  real expense amount during parsing.

### 11.2 `Timesheet  Report Jan 26.xlsx`
- Single sheet. Row 0 = stray totals; Row 1 = headers; data from row 2.
- Headers: `Emp Code | Emp Name | Date | Client Name | Task | Duration |
  (day-fraction) | Description | Submission Date | Approved/Rejected By |
  Draft/Requested | Reporting Manager`.
- `Duration` = "HH:MM" string; next column = day fraction (08:00 → 1).
- 4,252 rows, **133 employees, 385 clients, 135 tasks**.
- ⚠️ Date range **21-Dec-2025 to 20-Jan-2026** — the firm's "month" appears to
  run 21st→20th, NOT calendar month.
- ⚠️ `Reporting Manager` has **28 distinct names** — far more than the 4
  managers listed (includes senior partners, the 4 managers, `#N/A`, and ~15
  others e.g. Bhavik Shah, Rinku Patel, Arpit Khandelwal, Karan Vakharia).
- Client Name includes non-client values: `Non Billable`, internal entity
  names (`Bilimoria Mehta & Co`) for office/admin tasks.

### 11.3 `salary.xlsx`
- Single sheet. Headers: `Month | Name | Cost centre | Entity | E/CA/CMA |
  Salary Paid | Reimbursement | Partner 2`. 180 rows.
- Cost centre values: `PM, KS, JV, AM, SD, VK, AL, Office, PG` (⚠️ `PG` not in
  the partner list; `MS` absent in sample).
- Entity values: `Bilimoria, Corporate, Advisors` (⚠️ short names — need
  mapping to the 6 full entity names).
- `E/CA/CMA` = staff category: `Employees, CA Article, CMA Article`.
- ⚠️ Same employee appears on **multiple rows**, already split across cost
  centres (operator pre-allocates cost centre in this sheet).
- `Reimbursement` column present but mostly empty.

### 11.4 Key gaps blocking the core design
- **No Sales Register sample** — needed for revenue, services,
  client→cost-centre, and the voucher→`Partner–Manager` mapping.
- Reporting-manager hierarchy unclear (28 names vs 4 managers).
- Period alignment unclear (timesheet 21→20 vs calendar month files).
- Entity short-name → full-name mapping needed.
- `PG` cost centre and `Office` cost centre meaning to confirm.

---

## 12. Data Model (local SQLite database)

### Master tables (full add/edit/delete; "soft delete" via `active` flag so
### history is preserved)
- **entities** — id, name, aliases (for matching file names), active.
- **cost_centres** — id, code (PM/KS/JV…), name, type (`partner` | `office`),
  active. "Office" is a built-in overhead cost centre.
- **managers** — id, code (RM/SR/UV/GS…), name, cost_centre_id, active.
- **employees** — id, emp_code, name, category (Employee | CA Article |
  CMA Article), manager_id (nullable), default_cost_centre_id (nullable),
  active.
- **clients** — id, canonical_name, cost_centre_id, active.
- **client_aliases** — id, client_id, alias_text, source (tally | timesheet).
  Powers fuzzy matching memory.
- **services** — id, name, active.
- **targets** — id, financial_year, cost_centre_id, target_amount
  (optional month-wise breakup).

### Transactional tables (historical, every row date/period-tagged)
- **import_batches** — id, entity_id, file_type, file_name, period (year-month),
  imported_at, status (staged | committed).
- **vouchers** — id, batch_id, entity_id, date, vch_type, vch_no, party_name,
  client_id, gross_amount, tax_amount, net_amount, description, ledger_head,
  raw_cost_centre, kind (sales | expense).
- **voucher_splits** — id, voucher_id, amount, cost_centre_id, manager_id,
  service_id, note. Every voucher has ≥1 split; default = one split for the
  full amount. This is the `Partner – Manager` attribution + the split feature.
- **timesheet_entries** — id, batch_id, emp_code, emp_name, date, client_raw,
  client_id, task, hours, day_fraction, reporting_manager, description,
  is_billable.
- **salary_entries** — id, batch_id, month, employee_name, cost_centre_id,
  entity_id, category, salary_paid, reimbursement.

### Mapping memory tables
- **column_templates** — id, entity_id, file_type, layout_signature,
  column_map (JSON). The flexible import-template engine.
- Client→cost-centre lives on `clients`; voucher→Partner-Manager on
  `voucher_splits`; timesheet-client→Tally-client via `client_aliases`;
  employee→manager+cost-centre on `employees`. All editable anytime; changes
  apply going forward and do not corrupt committed history.

### Derived at report time (never stored stale)
- Hourly rate = employee's total pay for the month ÷ total timesheet hours that
  month.
- Labour cost per client = hours × hourly rate; rolled to cost centres.
- Cost-centre / entity / service / Partner-Manager P&L.

---

## 13. Import & Mapping Flow

1. Operator picks a file + entity + file type (sales / purchase / timesheet /
   salary). Type can be auto-suggested.
2. System checks the layout signature. New layout → operator maps columns to
   canonical fields once; template saved and auto-reused thereafter.
3. Parser extracts rows into a **staging** area (nothing committed yet).
4. System resolves clients (fuzzy match), cost centres, employees, services.
   Anything unknown/ambiguous is queued for the operator to confirm/map.
5. Vouchers shown in a review grid: each defaults to one split = full amount.
   Operator can split a voucher and assign each split a `Partner – Manager`
   string (and service).
6. Operator commits → data written to DB, tagged by calendar-month period.

---

## 14. MIS Workbook Layout (formula-driven Excel)

Generated workbook sheets:
- **Cover / Dashboard** — headline KPIs, period selector, target vs actual.
- **Cost Centre P&L** — per senior partner: revenue, direct cost, labour,
  overhead (toggle), profit, target, variance.
- **Partner–Manager P&L** — per `PM – RM` style string.
- **Entity P&L** — per associated entity.
- **Service MIS** — revenue/cost by service.
- **Comparatives** — current vs chosen prior period(s) / prior year.
- **Data sheets** (hidden-ish): Vouchers, Voucher Splits, Labour Allocation,
  Salary, Mappings — raw figures.
- Report sheets reference data sheets with live formulas (`SUMIFS`, etc.) so
  every presented number is auditable and recalculates if data is tweaked.

---

## 15. Build Phases

1. **Project skeleton** — Python app structure, SQLite schema, packaging setup.
2. **Master data management** — CRUD UI for entities, cost centres, managers,
   employees, clients, services, targets.
3. **Import engine** — flexible column-template mapping + parsers (Tally
   sales/purchase, timesheet, salary).
4. **Resolution & review** — fuzzy matching, unknown-item prompts, voucher
   split & Partner-Manager assignment UI.
5. **Calculation engine** — hourly rate, labour allocation, P&L roll-ups,
   office-expense allocation, targets.
6. **MIS generator** — formula-driven Excel workbook with all views.
7. **Historical comparison** — period selection & comparatives.
8. **Packaging** — Windows installer (.exe), no Python needed on target PC.
