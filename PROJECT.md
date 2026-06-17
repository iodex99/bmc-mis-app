# Automated MIS Generator — Bilimoria Mehta & Co.

> Living document. Updated as we discuss. Last updated: 2026-06-12
>
> Current version: **v0.3.81** ([release history on GitHub](https://github.com/iodex99/bmc-mis-app/releases))

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

## 16. Post-launch iterations (v0.2.0 → v0.3.71)

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

### v0.3.81 — Dashboard tables: click-to-sort + filter box

Every dashboard table (Full P&L, budget detail, entity, service,
partner–manager, client billing, employee register) is now interactive:

* **Click any column header to sort.** Numeric columns sort by value —
  parsed from the formatted cell ("₹-9,77,331" → −977331, "63.7%" →
  63.7), with blanks ("—") pushed to the end — text columns sort
  alphabetically. Direction toggles on each click with a ▲/▼ indicator,
  and the **TOTAL row stays pinned** at the bottom.
* **Filter box on long tables** (auto for >10 rows, e.g. Client
  Billing): type to show only matching rows; the TOTAL stays visible.

Pure client-side over the rendered cells — no figures recomputed, so the
table still ties to the workbook. Sort arrows and filter boxes are hidden
when printing. Verified the parsing/sort logic and confirmed the wired
markup (7 sortable tables, filter box) in the rendered DOM.

### v0.3.80 — Dashboard: fix horizontal-bar tooltips + per-chart Sort / Top-N

Two dashboard follow-ups:

* **Tooltips on horizontal bars showed the wrong value** ("₹0", "₹1").
  Chart.js puts the value on the axis OPPOSITE the category (index) axis,
  so a horizontal bar (``indexAxis:'y'``) carries its value on
  ``parsed.x`` — the old callback read ``parsed.y``, which is the category
  INDEX (0, 1, …). New ``valueOf()`` picks the axis from the chart's
  ``indexAxis`` (and treats doughnut ``parsed`` as the value). Verified for
  horizontal bar, vertical bar, doughnut and count charts.
* **Per-chart Sort + Top-N controls.** Every ranking chart (Cost Centre
  P&L, Budget vs YTD, Entity, Service, Partner–Manager, Client Billing,
  and the revenue donuts) now has a small Sort (Default / Value ↓↑ /
  Name A–Z, Z–A) and Show (All / Top 5–30) toolbar. It re-derives the
  view client-side from the chart's stored original data — no figures
  recomputed. Client Billing now feeds the full client list with a
  Top-15 default. Time-series charts (monthly trend, headcount by period,
  overhead trend) keep their natural order and have no controls. Controls
  are hidden when printing.

### v0.3.79 — Interactive HTML dashboard generated alongside the Excel MIS

Operator asked for a board-room-ready visual dashboard, downloaded with
the workbook, covering everything the Excel does, with the figures
guaranteed not to drift from the workbook.

* **New module `app/services/dashboard.py`.** Renders a self-contained
  ``<name>_Dashboard.html`` next to the saved ``.xlsx`` (wired into the
  Generate page; a dashboard failure can't lose the workbook). The
  Generate dialog offers to open both.
* **Same numbers, one calculation path.** It renders from the SAME
  :class:`MISData` the workbook is built from — there is no second
  aggregation. The FY-to-date budget view shares a new
  ``report.budget_monthly_data`` helper with the Excel "Budget vs Monthly
  Sales" sheet, and money uses the same ``fmt_inr`` Indian grouping. So
  every figure ties to the workbook by construction.
* **Coverage.** KPI cards (Revenue, Cost, Net Profit, Margin, Target,
  Variance) + sections for Cost Centre P&L (revenue/cost/profit bars,
  revenue-share donut, stacked cost composition, full table), Budget vs
  Monthly Sales (budget-vs-YTD bars, monthly trend, FY-to-date table),
  Entity P&L, Service MIS, Partner–Manager, Client Billing (top-15 bar +
  full table), and Employee Register (headcount movement, headcount by
  cost centre, office-overhead trend). Sticky section nav + a Print/PDF
  button; clean navy/blue board-room styling.
* **Offline by default.** Chart.js is vendored under ``app/assets`` and
  **inlined** into the HTML (CDN only as a fallback), so the file opens
  anywhere with no internet and nothing to install. ``build.py`` bundles
  the asset via ``--add-data``; ``config.resource_path`` resolves it in
  both dev and the frozen exe (``sys._MEIPASS``).

Verified end-to-end: generated the workbook and dashboard from one
dataset and confirmed the KPI / cost-centre figures match, and
rendered the HTML headless to confirm the charts and layout.

### v0.3.78 — Annual Targets FY dropdown extends further forward

The v0.3.77 financial-year dropdown only reached current FY + 3
(2029-30). Widened the forward window to current FY + 30 (now through
~2056-57) so the list keeps going for years ahead. Still 3 years back,
still an editable combo for anything beyond the window, still merges any
FY already in use.

### v0.3.77 — Budget run-rate column, FY dropdown for targets, voucher totals

Three operator asks:

* **Budget vs Monthly Sales — last column is now a required run-rate.**
  The old "Avg / Active Month" (YTD ÷ months-with-sales) is replaced by
  "Avg / Remaining Month": **Variance vs Budget ÷ months left in the FY**
  — i.e. the average monthly sales each partner must still book to hit
  the annual budget. The header shows the remaining-month count
  (e.g. "Avg / Remaining Month (10)"); a full-FY run (0 left) shows 0.
* **Annual Targets — financial year is a dropdown.** No more typing
  "2026-27" by hand (the source of the "2026 - 27" mismatch fixed in
  v0.3.73). The Targets master now offers a dropdown of financial years
  (current ± 3, plus any already in use, newest first); still editable
  for an out-of-range year, and normalised on save. Targets stay annual,
  one row per (cost centre, FY).
* **Review & Map → Vouchers: a live Totals bar.** Under the existing
  Entity / Period / Kind / Status / Search filters, a totals line now
  sums the filtered vouchers — Sales (net), Expenses (net), Gross and
  Tax — so the operator can reconcile the preview against Tally's
  register totals BEFORE generating the Excel MIS. Recomputes on every
  filter / search change.

### v0.3.76 — Support the "Other Income Register" (Qualzen MF commission)

Operator's ``QZ OTHER INCOME.xlsx`` wasn't being picked up. It's a Tally
*"Other Income Register"* (voucher type "Other Income") — the Qualzen
entity's MF-commission income. Structurally it's identical to a Sales
register: the party is debited, an income ledger is credited, and the
amount is tagged to a partner cost centre (VK here). Only the banner went
unrecognised, so ``detect_kind`` returned ``None`` and the importer
offered no auto-mapping.

* **Banner now recognised** — ``other\s*income`` added to the sales-side
  banner regex, so "Other Income Register" detects as a revenue register,
  auto-maps its columns (which sit further right than a normal sales
  export) and auto-resolves the Qualzen entity (already in the masters).
  Kept tight: a bare "Income Register" does NOT match, only "Other
  Income".
* **Routes to revenue** — "Other Income" vouchers default to the sales
  side (credit, +ve), so the ₹3,76,000 lands in partner VK's income and
  flows through every downstream view: Cost Centre P&L revenue,
  Partner-Manager income line (category "Income"), Entity P&L (Qualzen),
  and the Service MIS (as an "Other Income" service line).

Notes: the import dialog labels it a "Sales register" (it shares the
revenue code path — cosmetic only), and the booked party "Other Income
( MF Comission )" shows as an unmapped client in Client Billing since
it's income, not a client sale. Verified end-to-end: 5 vouchers, net
₹3,76,000, and all 14 other reference registers parse unchanged.

### v0.3.75 — "New Sale" register undetected; harden Tally totals-row parsing

Operator reported the foreign-currency ``Advisor new sale.xlsx`` (MASD
Advisors) wasn't picked up. Investigation showed the foreign currency
itself was never the problem — each FC voucher carries its converted INR
value in the Debit/Credit Amount columns, and the FC detail sub-rows
(``| 7963 | @ | 93.09 |``, i.e. amount × rate) have no value in the
amount columns and no Dr/Cr marker, so the parser already skips them and
keeps the INR figure. Verified across both FC files in the reference set
(``Advisor new sale`` ₹7,41,275.67; ``ADVISOR CREDIT NOTE`` −₹10,932.35).

Two real bugs found and fixed:

* **Banner went undetected.** MASD exports a *"New Sale Register"*
  (voucher type "New Sale") — singular "Sale". The sales banner regex
  required "sales", so ``detect_kind`` returned ``None``; the importer
  then skipped auto-mapping entirely and the operator saw no data. The
  regex now accepts ``sales?`` (singular or plural), so "New Sale
  Register" detects as sales, auto-maps its columns, and auto-resolves
  the MASD entity. Word-boundary anchoring keeps "Wholesale"/"Resale"
  from false-matching.
* **Trailing "Total" row mis-parsed.** Tally closes each register with a
  ``Total :`` row that still carries a Dr/Cr marker + amount. The parser
  treated it as a cost-centre tag on the last voucher's final ledger
  line, attaching a bogus ``Total :`` cost centre (seen in 5 of the
  reference registers). It happened to land on a tax line every time, so
  revenue attribution was unaffected — but it would have misattributed a
  plain fee line. A new ``_is_total_row`` guard skips these rows; the
  in-flight ledger line is still committed by the end-of-loop flush.

Confirmed across all 14 reference registers (sales, sales-D/BR, credit
note, debit note, purchase): every net total is identical to before, and
no bogus cost centres remain.

### v0.3.74 — Revenue sheet: "Voucher No" column relabelled "Invoice No"

Operator ask: on the generated MIS's Revenue data sheet the second
column (the sales voucher's number) reads more naturally as the
**invoice number**, since a Sales Register row IS the firm's invoice.
Header-only change — the column stays in position B, so every SUMIFS in
the P&L sheets (which key on column letters / cell values, never the
header text) is unaffected. The Expenses sheet keeps its own separate
"Voucher No" / "Invoice No" columns unchanged.

### v0.3.73 — Annual targets read 0 in the MIS — financial-year format mismatch

Operator entered annual targets per cost centre in the Targets master,
but the generated MIS showed **0** in the Target column (and the
Budget-vs-Sales sheet's Annual Budget). Root cause: the operator typed
the financial year as ``2026 - 27`` (spaces around the hyphen), while
``financial_year()`` derives the tight ``2026-27`` from the selected
periods — and both target lookups did an **exact string match**, so a
stray space silently zeroed the target.

* **New ``normalize_fy()`` helper** canonicalises loosely-typed years
  (``2026 - 27``, ``2026-2027``, ``2026/27`` → ``2026-27``).
* **Both readers fixed** to match on the normalised year: the Cost
  Centre P&L Target column (via ``calc``) *and* the Budget-vs-Sales
  sheet's Annual Budget (``report``). This in turn corrects the
  **Variance** column (Revenue − Target) on the Cost Centre P&L and the
  budget-variance column on the Budget sheet, which were both computed
  off the zeroed target.
* **Input is normalised on save** in the Targets master, so new/edited
  entries are stored canonically.
* **Migration 13** rewrites existing rows (``2026 - 27`` → ``2026-27``),
  de-duping first so the strip can't trip the UNIQUE constraint — the
  operator's already-entered targets resolve without re-typing.

Verified end-to-end against a copy of the operator's database: migration
canonicalises all 7 rows with amounts intact, and a 3-month MIS resolves
CC1's ₹4.5cr annual target to the expected ₹1.125cr pro-rated figure.

### v0.3.72 — Fix blank Direct Expense on Service MIS / Entity P&L; Headcount table beside the summary

Two operator-reported issues:

* **Direct Expense column came out blank on the Service MIS (and
  Entity P&L) sheets.** Root cause: the v0.3.69 Expenses-sheet layout
  inserted *Invoice No* (C) and *Type of Expense* (H), pushing the
  *Amount* column from H to **J**. The Cost Centre P&L and Comparatives
  SUMIFS were updated at the time, but ``_simple_summary`` — the shared
  builder behind both the Service MIS and Entity P&L Direct-Expense
  columns — was missed and kept summing column **H**, which is now the
  *Type of Expense* TEXT column. Summing text returns 0, so every
  Direct-Expense (and therefore Net) cell read blank. Now sums column J.
  Revenue was unaffected (the Revenue sheet's Amount stayed at H). The
  Net / TOTAL cells are formula-derived, so they self-correct.
* **Employee Register — "Headcount by cost centre" now sits beside the
  summary.** It was stacked at the very bottom of the sheet, below the
  full roster; moved to the top-right (column I, aligned with the
  summary header row) so the operator reads both summary tables without
  scrolling past the roster. COUNTIFS retargeted to the table's new
  Cost-Centre (I) and Period (J) columns.

Verified by generating a workbook from synthetic facts: the Service MIS
Direct-Expense SUMIFS now reproduces the expected ₹14,000 total, and the
headcount title/header/body land at I3/I4/I5 with correct roster
references.

### v0.3.71 — Update data-safety: purge restricted to the app's own payload

Operator asked for explicit assurance that updates can never lose
data. Audit of the whole chain:

* **The database is structurally out of reach.** ``mis.db`` (every
  master, mapping, voucher, timesheet, salary row) + ``exports/``
  live in ``%LOCALAPPDATA%\BMC MIS`` — the updater only ever writes
  inside the install folder. Verified by test: a stand-in data home
  is bit-identical after a full helper run.
* **Schema upgrades are additive-only.** Re-verified the migration
  runner: a populated v11-schema DB upgraded by the new build keeps
  every row (vouchers / splits / timesheet / salary / clients all
  intact) while gaining the v12 ``invoice_no`` column.
* **One real hole found and closed.** The helper's single
  ``robocopy /MIR`` over the whole install folder PURGES anything
  not in the new build — so a workbook the operator saved next to
  the exe (or any stray Tally file / notes folder) would have been
  silently deleted on the next update. The helper now mirrors-with-
  purge ONLY the app's own ``_internal`` payload and copies the
  install root with ``/E`` (overwrite ours, never delete theirs);
  an unexpected build layout falls back to a full no-purge copy.

Verified with a live helper run (hidden, production flags): exe +
``_internal`` updated, stale payload purged, while the operator's
``My MIS April.xlsx``, a notes folder, and even a paranoid
``data\mis.db`` sitting beside the exe all survive untouched.

### v0.3.70 — Updater: no more stray terminals, no more random app-close

Operator report: "when the app starts, or even when I click check
updates, it sometimes closes automatically… when I click install
update it starts this terminal, then I have to press Ctrl+C, then
another terminal opens and runs a script, then the app gets updated."
Screenshots showed a console window titled ``find "4080"`` (the PID
wait) and a second one running robocopy. Three distinct bugs:

**1. Random app-close on check = the QThread crash class, again.**
Both the launch-time silent check (``main_window``) and the Settings
page's check/download used ``QThread`` + ``moveToThread`` +
cross-thread signals — the exact pattern that intermittently killed
the app during import commits on the operator's machine (fought
v0.3.61→63, eliminated v0.3.64). The updater never got the same
treatment. Both paths now use a plain ``threading.Thread`` that only
puts plain tuples on a ``queue.Queue``; a ``QTimer`` polls the queue
ON the UI thread and does all widget work there (progress ticks
included). No Qt object is ever touched off the UI thread, so the
PySide6 signal-delivery crash can't fire.

**2. Visible terminals + the Ctrl+C wedge = DETACHED_PROCESS.**
``apply_update`` launched the helper with ``CREATE_NO_WINDOW |
DETACHED_PROCESS``. A detached cmd has NO console at all, so every
console-subsystem child (tasklist, find, robocopy) allocated its own
VISIBLE window — those were the operator's two terminals — and the
wait loop wedged until Ctrl+C. Helper now launches with
``CREATE_NO_WINDOW`` only: cmd gets a real but invisible console all
children inherit. Zero windows, pipes work.

**3. Helper script hardening** (``build_helper_script``, now a pure
function for testability):

* External tools fully qualified to ``%SystemRoot%\System32`` —
  a bare ``find`` resolves through PATH, and Git-for-Windows' GNU
  find shadows the Windows one (caught live in testing: the PID
  wait exited instantly because GNU find can't parse the syntax).
* ``timeout /t`` → ``ping -n`` sleeps. ``timeout`` exits immediately
  ("Input redirection is not supported") when stdin is redirected —
  which it always is for a hidden helper.
* The PID wait is BOUNDED (~120 s) — logs "gave up" and proceeds
  instead of spinning forever; robocopy's /R retries cover a
  briefly-locked exe.
* Handle-release pause trimmed 5 s → 2 s so the app reappears
  faster after the silent install.

Verified end-to-end with a real process stand-in: helper (launched
hidden, exactly like production) waits the full lifetime of the fake
app, mirrors the new build, purges stale files, reaches the relaunch
step, logs all six phases — no interaction, no window. Headless Qt
tests cover check (update / up-to-date / network-error), download
progress ticks, and the launch-time auto-check pill.

### v0.3.69 — Multi-CC splits, invoice no, expense bifurcation, Employee Register, books-driven overhead

One coordinated release covering the operator's eight-point list.

**1. Parser: multi-cost-centre voucher splits (the big one).** A
ledger line followed by SEVERAL Dr/Cr cost-centre tags ("PROFESSIONAL
FEES 3,60,000" tagged "Mr. Shreyans Dedhia 1,60,000" + "Mr. Vishal
Kothari 2,00,000") was keeping only the FIRST tag — ``flush_pending``
fired on the first tag row, so the second arrived with
``pending_line=None`` and was silently dropped. The whole 3,60,000
landed on Shreyans. Tags now accumulate per ledger line: N tags → N
splits, each with the tag's own amount; a single partial tag (or tags
that don't sum to the line) leaves the remainder as an unassigned
split so Review flags it instead of hiding it. Verified on the real
``BMCA Sale.xlsx``: Sycon voucher MUM/26-27/1 now produces SD 1,60,000
+ VK 2,00,000 + SD 4,543 OPE; file-level net unchanged to the paise.
NOTE: already-imported vouchers keep their old single-CC splits (dedup
skips re-imports) — delete the affected batch on the Records page and
re-upload to pick up the fix.

**2. Invoice number from "New Ref" (migration v12).** The detailed
register export carries the bill reference on a "New Ref" sub-row
(party side, opposite Dr/Cr marker — previously skipped silently).
Captured per voucher ("New Ref" preferred, "Agst Ref" fallback,
multiple refs joined), stored in ``vouchers.invoice_no``, shown in the
import preview and on the Expenses sheet right after Voucher No.
78/84 vouchers in the operator's real purchase file carry one.

**3. Party → Client on every register.** Expense/revenue facts now
carry ``party_name``; the Client column (Review vouchers tab, Revenue
/ Expenses sheets, Client Billing rows) shows the master canonical
name when resolved and falls back to the raw party text otherwise —
no more "(unmapped)" wall on the Expenses sheet. Genuinely-new names
still queue in Review → Clients exactly as before.

**4. Type of Expense column.** Every expense row is bifurcated:
service name contains "professional" (but not "professional tax") →
``Professional Fees`` (direct); everything else → ``Indirect
Expense``. New column after Service on the Expenses sheet; the P&Ls
SUMIFS against it.

**5. Partner-Manager P&L restructure.**

* "Other Direct Expenses" → **Professional Fees** (Type-filtered
  SUMIFS), plus a **Reimbursement Expenses** row so Total Direct Costs
  (= Salary + Professional Fees + Reimbursements) still ties with the
  Cost Centre P&L's Direct Expense column.
* The overhead block above Net Profit is split in two: **Office
  Overhead (allocated)** (per-employee share, Salary-sheet SUMIFS) and
  **Indirect Expenses** (the partner's own indirect costs, Expenses-
  sheet SUMIFS). Net = Gross − Overhead − Indirect.

**6. Employee Register sheet.** Built from the stored timesheet rows:
per-period summary (active employees = filed hours that period; new
joiners / exits vs the previous month's timesheet — read from the DB
even when that month isn't part of the report), full roster with home
CC + movement, and headcount-by-cost-centre — all COUNTIFS-driven off
the roster. First month with no prior timesheet shows "(no data)"
instead of declaring everyone a joiner.

**7. Office overhead = books ÷ headcount (replaces the master).** The
``fixed_office_overhead`` master tab is gone (table stays; nothing
reads it). Per period: ``overhead/employee = Office-CC indirect
expenses ÷ active employees``. Each active employee carries one
Overhead-type Salary-sheet row on their home CC; a single negative
offset row on Office backs the pool out (it already sits in Office's
Direct Expense — without the offset the firm total would double-count).
The old allocate-by-revenue/equally toggle on the Generate page is
retired too.

**8. Fully live formula chain.** Expenses (Type/CC/Period columns) →
Employee Register (pool SUMIFS, headcount COUNTIFS, per-employee
ROUND) → Salary sheet Overhead rows (SUMIFS into the register) →
both P&Ls (SUMIFS on Type="Overhead"). Tweak any office expense row
and the entire overhead cascade recomputes inside Excel. Verified
with the ``formulas`` engine on the real Apr+May files: workbook
revenue / cost / profit equal the calc engine to the rupee, register
counts and per-employee overhead evaluate correctly, and the P&L's
Professional Fees / Indirect rows match the classifier's totals.

### v0.3.68 — Salary sheet: three-CC representation for clarity

Operator pointed out that the single "CostCentre" column on the
Salary sheet — while computing the right destination — was opaque.
Reading a row "Bhavya / ABC / VK" you couldn't tell at a glance why
SD's employee landed on VK without cross-referencing the client
master. The mechanics were correct since v0.3.57 (billable hours
follow the client's CC because that's where the revenue lands),
but the transparency was missing.

Three CC columns on the Salary sheet now:

* **Charged To** (was "CostCentre", same column C — SUMIFS unchanged
  in semantics) — where the cost actually lands.
* **Client CC** (NEW, col F) — the CC the worked-on client belongs
  to. Blank for residual / non-billable / overhead rows.
* **Home CC** (NEW, col G) — the employee's home CC from the master.
  Always populated; differing from "Charged To" instantly signals
  cross-partner work.

A row reads top-to-bottom: "Bhavya (Home SD) worked on ABC (Client
CC VK) → 4 h charged to VK." No master cross-reference needed.

Column shift cascade: Hours F→H, Amount G→I, Type H→J. All five
SUMIFS sites that reference the Salary sheet were repointed:
Cost Centre P&L Salary Cost + Allocated Overhead; Partner-Manager
P&L labour_sumifs + overhead; Comparatives comp labour. The
labour_sumifs in the Partner-Manager P&L additionally picked up a
Type="Salary" filter so the Overhead rows (v0.3.67) don't
double-count under the salary line.

Verified with the operator's example: Bhavya 4 h on ABC ⇒ row
shows Charged VK / Client CC VK / Home CC SD. Isha 6 h on XYZ ⇒
Charged SD / Client CC SD / Home CC VK. Per-partner sums:
VK ₹49,596 salary + ₹5,000 overhead, SD ₹50,403 salary + ₹5,000
overhead.

### v0.3.67 — Fixed office overhead reaches Cost Centre P&L + variance off revenue

Three coordinated changes:

**1. Allocated Overhead column now reflects the master-defined fixed
office overhead.** Pre-v0.3.67 the per-employee overhead from the
``fixed_office_overhead`` master got rolled into the per-employee
salary RATE in ``_build_labour_facts``, which meant the overhead
silently bifurcated across whichever partner's clients an employee
worked on — useful in some costing theories but NOT what the
operator wants. They told us plainly: "the allocated overhead is a
fixed cost incurred by each employee in that particular month, so
it will be an expense to the respective cost centre of the employee,
which you can find from the emp master." So:

* ``calc.py`` — salary rate uses salary only (not salary + overhead).
* Each employee now gets ONE additional ``is_overhead=True`` labour
  fact per period, entirely on their home CC, with no timesheet
  bifurcation.
* Salary sheet gains a ``Type`` column ("Salary" / "Overhead").
* Cost Centre P&L "Salary Cost" column = SUMIFS over Type="Salary".
* Cost Centre P&L "Allocated Overhead" column = SUMIFS over
  Type="Overhead" — fully formula-driven.
* Partner-Manager P&L overhead row now SUMIFS-driven too (was a
  baked numeric value).

**2. All MIS cells that can be formula-driven now are.** Auditing
the Cost Centre P&L and Partner-Manager P&L confirmed every Salary
Cost / Allocated Overhead reference now uses SUMIFS against the
data sheets rather than baked values from the calc engine. The only
non-formula numbers left are: Targets (master input), and master
lookup labels — everything else recomputes when data sheet rows
change.

**3. Variance = Revenue − Target.** Pre-v0.3.67 was
``Profit − Target`` which conflated achievement-against-revenue-
target with operating profit margin. Changed to ``=C{r}-I{r}``.

Verified with a 2-employee × ₹50k salary + ₹10k overhead each
scenario: AM home gets ₹98,387 salary + ₹20,000 overhead, JV (where
Emp1 logged 8h on a JV client) gets ₹1,613 salary and ZERO
overhead. Variance formula correctly reads ``=C6-I6`` on the AM row.

### v0.3.66 — Review queue shows purchase + reimbursement parties
Operator reported parties from the Purchase Register weren't appearing
in the Review & Map tab even though the corresponding client master
rows didn't exist.

Root cause: ``resolution.unresolved_clients`` hard-coded
``WHERE kind = 'sales'`` when scanning ``vouchers``, and never
queried ``reimbursements`` at all. v0.3.46 had extended the
auto-LINK pass to all voucher kinds; the Review LISTING never
caught up. v0.3.62 added the reimbursements table; the listing
never knew about it either.

Fix: the unresolved list now pulls from all four sources:

* ``vouchers WHERE kind = 'sales'``       → labelled "Sales"
* ``vouchers WHERE kind = 'expense'``     → labelled "Purchase"
* ``timesheet_entries``                   → labelled "Timesheet"
* ``reimbursements``                      → labelled "Reimbursement"

All four merged into the existing ``raw → count + sources`` aggregator
and sorted by count descending so the high-volume entries surface at
the top regardless of which table they came from.

Most purchase-register parties ARE vendors and don't need mapping —
they just stay in the list as unmapped. But the few that are
legitimately clients (or recharged-to-client expenses tracked
per partner) now show up so the operator can map them.

Verified with a 4-source synthesized scenario: 5 unresolved entries
returned, including the 2 purchase-side parties and 1 reimbursement
party that v0.3.65 would have hidden.

### v0.3.65 — Records page counts reimbursement rows
Operator imported a 708-row reimbursement sheet on v0.3.64. Import
preview showed "Parsed 708 records", commit succeeded, but the
Records page showed the batch as "0 rows" — looked like the data
had been lost.

Diagnosis: ``records.list_import_batches`` (the SQL feeding the
Records list) only sums vouchers + timesheet_entries + salary_entries
per batch. The v0.3.62 reimbursements table was never wired in.
Verified with a 708-row synthesised import: rows ARE in the DB
(``SELECT COUNT(*) FROM reimbursements`` returns 708), they just
weren't being counted in the display.

Fix: extended the SQL to also count ``reimbursements`` per batch
and added the new field to the Python total used by both the Records
page summary line and the Delete-confirmation prompt.

After v0.3.65, the operator's batch #18 will read "708 rows" instead
of "0 rows" without re-importing — the data was always there.

### v0.3.64 — Drop QThread, commit on UI thread (stop the crash for good)
Operator still seeing commit crashes / "not responding" after v0.3.63:

* Reimbursement upload → Importing → app closes
* Tally upload → Importing → "not responding"

v0.3.61 introduced a ``QThread`` + ``_CommitWorker`` to keep the UI
responsive during long commits. v0.3.62 still used a nested
``QEventLoop`` to block on the worker. v0.3.63 swapped to a callback
pattern matching ``settings_page.py``'s ``_run_thread``. The
smoke-tests passed on the dev machine each time. On the operator's
machine all three shapes crashed the app AFTER the commit landed in
the DB (records present on next launch) — strongly suggests a
``QObject`` lifetime / cross-thread signal-delivery edge case in
some PySide6 builds that we can't reproduce or debug remotely.

v0.3.64 drops threading altogether. ``_commit`` now runs the
commit synchronously on the UI thread and pumps the event loop via
``QApplication.processEvents()`` inside the progress callback
between stages. The progress dialog still appears and stays
responsive throughout. For a 5k-row timesheet that's ~275ms of
work (v0.3.61 perf measurement) — imperceptible. For larger
files the UI briefly freezes but the app never dies.

A reliable simple flow beats a fast threaded flow that crashes.

Removed: ``_CommitWorker`` class, ``QThread``/``QObject`` imports,
``self._commit_thread``/``self._commit_worker`` instance attrs,
the ``_on_commit_finished`` callback (folded back into ``_commit``).

Verified end-to-end: ImportPage constructs, reimbursement parser
emits 2 rows from a 2-row sheet, ``commit_result`` runs with all 7
progress stages, batch report counter populated, rows actually land
in the DB.

### v0.3.63 — Fix v0.3.61 commit-then-close crash + v0.3.62 reimbursement parser
Operator reported two regressions:

1. The reimbursement sheet uploaded fine through the column-mapping
   dialog but no preview rendered and the Commit button stayed greyed
   out.
2. Tally imports completed (records actually landed in the DB) but
   the app closed immediately after the commit.

Two unrelated bugs.

**Bug 1 — ``ParsedReimbursement`` was never imported in
``parsers.py``.** The new ``parse_reimbursement`` function (v0.3.62)
referenced ``ParsedReimbursement(...)`` to build its result rows, but
the import statement only pulled the other four model classes. So
the moment the parser tried to construct its first row it raised
``NameError`` — silently inside ``parse()``, since the exception
propagated to the UI layer where ``ResparseResult.row_count == 0``
left the Commit button disabled.

Fix: one-line import addition. Verified parsing 4 sample rows now
produces 4 ``reimbursement_facts`` end-to-end. Also added a
reimbursement preview branch in ``_render_preview`` so the operator
sees what was parsed in the preview table (Period, Date, Employee,
Client, Amount, Client Reimbursable) before clicking Commit.

**Bug 2 — nested ``QEventLoop`` in ``_commit`` (introduced v0.3.61).**
The post-commit flow was:

    progress.show()
    thread.start()
    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    loop.exec()
    progress.close()
    # … show result dialog …

Nesting a ``QEventLoop`` inside a click-handler-driven outer event
loop is fragile on Qt builds where the outer loop's slot stack
interacts with subsequent modal dialogs. On the operator's machine
that interaction was crashing the app after the worker completed
(but after the commit had already landed in the DB).

Fix: switched to the callback pattern (matches ``settings_page.py``'s
existing ``_run_thread`` helper). ``_commit`` now returns immediately
after starting the worker; the worker's ``finished`` signal fires
``_on_commit_finished(report, error)`` which runs the result-summary
dialog flow. The progress dialog is closed before the result dialog
opens, the thread is quit and ``deleteLater``'d cleanly, the Python
refs to the worker/thread are released. No nested event loops.

Also reported the new ``reimbursement_rows`` counter in the result
summary dialog ("N reimbursement row(s) added.").

Verified end-to-end: parser produces rows, worker commits without
error, all 7 progress stages emit, batch report counter populated,
ImportPage constructs cleanly.

### v0.3.62 — Reimbursements: dedicated upload sheet + partner P&L impact
Operator asked for a new dedicated reimbursement sheet (distinct from
the salary sheet's per-employee monthly aggregate), with these fields
on each row: period, employee, amount, client, ``client_reimbursable``
(yes/no). And a corresponding sheet on the generated MIS, AND for
the amounts to actually move profit.

End-to-end build — schema, parser, commit, calc, report.

**1. Schema (migration v11).** New ``reimbursements`` table:
``period | txn_date | employee_name | employee_id |
  client_raw | client_id | amount | client_reimbursable``
indexed on period. Raw client text resolves to a master row via the
existing client-resolution sweeps.

**2. Parser + file type.** New ``FILE_TYPE_REIMBURSEMENT`` + canonical
fields (``period``, ``date``, ``name``, ``amount``, ``client``,
``client_reimbursable``). New ``parse_reimbursement`` recognises yes /
y / true / 1 / t (case-insensitive) as ``True`` for the flag. Slots
into the existing column-mapping dialog automatically.

**3. UI.** New "Reimbursements (per-row sheet)" entry in the Import
page's file-type dropdown.

**4. Commit.** Batched ``executemany`` for the per-row INSERTs (same
perf pattern as v0.3.61's timesheet path). ``CommitReport`` gains a
``reimbursement_rows`` counter.

**5. Resolution.** ``_apply_client_norm_mapping`` and
``repoint_client_links`` extended to touch
``reimbursements.client_id`` alongside vouchers + timesheet_entries.
So a fresh reimbursement upload picks up master mappings, AND adding
a new client to the master back-links any stale reimbursement rows.

**6. Calc.** New ``MISData.reimbursement_facts`` built by
``_build_reimbursement_facts``:

* Cost-centre comes from the **client master** (the partner serving
  that client bears the cost).
* If the client isn't resolved yet, falls back to the employee's
  home cost-centre — same chain ``_build_labour_facts`` uses, so
  reimbursements never silently land on Office.

These facts are rolled into ``CostCentreLine.direct_expense`` on
each partner so the partner P&L's Direct Expense and Profit reflect
reimbursements automatically.

**7. Report.** New ``Reimbursements`` sheet:
``Period | Date | CostCentre | Employee | Client |
  Client Reimbursable | Amount``
Cost Centre P&L's Direct Expense formula extended to
``SUMIFS(Expenses) + SUMIFS(Reimbursements)`` so the live P&L picks
up the new sheet.

### How this affects profit

* ``client_reimbursable = YES`` — the matching revenue line comes
  through the Sales Register (as a ``Reimbursement`` / ``OPE``
  ledger), so the partner P&L nets the wash naturally. No special
  handling needed on the expense side.
* ``client_reimbursable = NO`` — the firm absorbs the cost. Partner's
  Direct Expense rises by the amount; Profit drops by the same.

Cost Centre P&L → Direct Expense → Total Cost → Profit chain
propagates automatically. Same for Comparatives + Dashboard KPIs.

### End-to-end test verified

4 reimbursement rows: ₹5k (Client A on AM, yes) + ₹2k (Client A on
AM, no) + ₹1.5k (Client B on JV, yes) + ₹1k (unmapped → falls to
Sahil's home AM, no).
``cost_centres`` rollup: AM direct_expense=8,000, JV
direct_expense=1,500. Reimbursements sheet rendered with all 4 rows
+ proper labels. Cost Centre P&L formula confirmed as
``SUMIFS(Expenses) + SUMIFS(Reimbursements)``.

### v0.3.61 — Import performance: 5k-row timesheets in under 300ms
Operator asked for the import path to scale cleanly: timesheets can run
5k rows per period and the data only grows. Pre-v0.3.61 the commit ran
synchronously on the UI thread with per-row INSERTs and per-row SQL
lookups, so a 5k-row import froze the app for many seconds with no
feedback.

Four coordinated fixes — measured 5,000-row timesheet commit goes from
"the app hangs for several seconds" to **275ms, ~18k rows/sec**, with
the UI staying responsive throughout.

**1. SQLite pragma tuning** (``database.connect``):

* ``journal_mode = WAL`` — Write-Ahead Logging. Cleaner crash recovery
  AND much faster for bulk inserts than the default rollback journal.
* ``synchronous = NORMAL`` — fsync only at WAL checkpoints. Safe under
  WAL; 5-10× faster commit speed.
* ``temp_store = MEMORY`` — sort / group / temp tables in RAM.
* ``cache_size = -65536`` — 64MB page cache.

**2. ``commit_result`` master caches.** Cost-centres, services and
entity aliases now load once into Python dicts at the top of the
commit. Per-row helper calls (``_cost_centre_id``, ``_ensure_service``,
``_entity_id``) used to do a SQLite SELECT each — at 5k timesheet rows
× 2 lookups apiece, that's 10k SELECTs replaced by dict lookups.

**3. ``executemany`` for timesheet + salary inserts.** A single bulk
batch instead of N individual ``execute`` calls. SQLite skips
re-parsing the SQL statement and reduces per-row transaction overhead.
Vouchers + voucher_splits stay row-by-row because the dedup branch
+ lastrowid dependency between voucher and its splits makes batching
fiddly; voucher imports rarely exceed a few hundred per file anyway.

**4. Worker thread + progress dialog.** ``commit_result`` now accepts
a ``progress_cb(stage, done, total)`` callback. New ``_CommitWorker``
in ``import_page.py`` runs the commit + post-commit resolution
sweeps on a ``QThread``; a ``QProgressDialog`` shows the current
stage and a determinate bar where applicable. The Qt event loop
keeps spinning so the dialog redraws and the app feels alive.

End-to-end stress test on a 5000-row timesheet:

    Elapsed: 275 ms
    Rate:    18,205 rows/sec
    Stages: Importing vouchers → Importing timesheet rows →
            Resolving cost-centre strings →
            Resolving client / employee names →
            Updating master inferences → Done
    Journal mode confirmed: wal

Should scale linearly from here — 10k rows ≈ 550ms, 50k rows ≈ 2.7s,
all without freezing the UI.

### v0.3.60 — Salary sheet: unresolved / non-billable timesheet rows go to employee's home CC
Operator screenshot showed Bhavik Shah (master CC = JV) with most of
his 8h/day timesheet entries booking to ``Office`` cost centre — only
one row (his explicit residual) landed on JV correctly.

Root cause: ``calc._client_cost_centre`` fell back to ``office_id``
whenever a timesheet row was:

* non-billable, OR
* billable but its ``client_id`` was NULL (unmapped client), OR
* billable but the resolved client's master row had no cost centre.

That meant every "office boy time logged against an unmapped or
internal activity" row dumped to Office, regardless of which partner
the employee actually reports under. Bhavik's 200+ hours of monthly
time scattered across Office while the residual logic correctly
sent his leftover hours to JV — visibly inconsistent.

Fix: ``_client_cost_centre`` now accepts a ``home_cc`` argument
(the employee's ``default_cost_centre_id`` from the master, with
the same fallback chain ``_build_labour_facts`` already uses for
residual rows) and routes all three "no explicit client CC" cases
to it instead of Office. Lines up the timesheet attribution with
the residual attribution: an employee's full monthly salary now
accrues to their home partner unless an explicit timesheet entry
on someone else's client overrides.

Smoke test on the operator's scenario:

    Bhavik Shah (home CC = JV)
    8h on 'Acme' (client master CC = AM)  → AM
    8h on 'Some Unmapped Client'          → JV  (was Office)
    8h on 'Another Unmapped'              → JV  (was Office)
    8h on 'Internal Training' (non-bill)  → JV  (was Office)
    208h residual                          → JV
    ---------------------------------------------
    AM     = 8h
    JV     = 232h
    Office = 0h    (was 24h before this fix)

Lines up with what the operator expected when she pointed out
"his master is JV — why is his time going to Office?".

### v0.3.59 — Salary sheet: distinguish residual from unmapped-timesheet rows
Operator reported the Salary sheet "only shows (residual / unallocated
time) in the Client column, the bifurcation is gone — it is not taking
from the timesheet" after v0.3.58. Investigation: timesheet rows ARE
in ``labour_facts`` (the data is correct), but v0.3.57 introduced a
label that converts ANY row with ``client_id IS NULL`` to
``(residual / unallocated time)``. Many of the operator's timesheet
rows have ``client_raw`` set (the office boy logged time against
"Bilimoria Mehta & Co" etc.) but their ``client_id`` was never
resolved to a master row — so the label made every unresolved
timesheet row LOOK like residual, hiding the actual bifurcation.

Two-part fix.

**1. Distinguish the three cases in ``labour_facts``.** Each fact now
carries:

* ``is_residual: bool`` — ``True`` only on rows the builder creates
  to absorb the leftover ``standard_hours - timesheet_hours``.
* ``client_raw: str | None`` — the original timesheet text, so when
  a timesheet row's ``client_id`` is still unresolved the Salary
  sheet can show the raw text + a hint instead of pretending it's
  residual.

Salary sheet's Client column now reads:

* resolved client → master canonical name
* unresolved timesheet → ``"<raw>  ← unmapped, link in Review tab"``
* true residual → ``"(residual / unallocated time)"``

**2. Auto-resolve clients at MIS-build time (skip fuzzy).** Added a
``skip_fuzzy=`` flag on ``apply_known_client_aliases`` and called it
from ``calc.compute`` so any master rows the operator added after
the last import get a chance to resolve their unmapped timesheet
rows during MIS generation. The fuzzy pass is deliberately skipped
at build time — operator can't see/audit new fuzzy auto-links there,
and the v0.3.50 fuzzy pass already runs as part of imports and
Master Data Add/Edit.

So if the operator does what the v0.3.58 docs suggested ("edit
Bilimoria Mehta & Co in Master Data and save without changes"),
v0.3.58's ``repoint_client_links`` handles the existing wrong-linked
rows. v0.3.59's build-time sweep handles the still-unlinked rows
for any client master row added later.

Smoke test verifies all four Salary-sheet cases produce the right
label and the right CC attribution.

### v0.3.58 — Salary sheet correctness: stale links auto-fix + Date col + Client Billing formulas
Operator reported the firm's own name "Bilimoria Mehta & Co" (when
logged on a timesheet by office boys / receptionists for internal
time) was showing up as "Dinaz Mehta" in the generated Salary sheet —
and even after adding the correct client to the master, the
mis-attribution persisted. Plus two smaller asks: a Date column on
the Salary sheet, and the Client Billing Grand Total as a formula.

**Five fixes — root cause + immediate corrective + UX polish.**

**1. Canonical names now always beat aliases in name-resolution.**
``_apply_client_norm_mapping`` was building its lookup with canonical
names first, then aliases — so when both held the same key, the
alias silently overrode. A stale fuzzy / Review-dialog mis-alias
would shadow the operator's authoritative master row indefinitely.
Swapped the insertion order: aliases first, canonical last so
canonical wins on collision. Same one-line fix applied to
``calc.py`` ``emp_index`` for the employee side.

**2. Adding a new master row now re-points stale links.**
New ``resolution.repoint_client_links(client_id, canonical_name)``:
deletes conflicting aliases for the new canonical, AND updates
vouchers / timesheet_entries whose raw name normalises to the new
canonical but currently points somewhere else. Wired into
``create_client``, ``bulk_import_clients``, and the Master Data
Add / Edit dialog (via a new ``RecordTab._post_save_repoint`` hook).
Direct corrective for the user's symptom: adding "Bilimoria Mehta
& Co" to clients now repoints every stale timesheet row away from
"Dinaz Mehta" automatically.

**3. Same repoint helper for employees**
(``resolution.repoint_employee_links``) — wired into the same
Master Data hook for the employees tab. Mostly belt-and-braces
now that fix #1 also covers ``emp_index``.

**4. Salary sheet: new ``Date`` column after ``Period``.**
Timesheet rows already carried ``txn_date``; surfaced it into
``labour_facts["txn_date"]`` and rendered in the Salary sheet via
the existing ``_fmt_date`` helper. Residual / unallocated rows
leave the cell blank. Cost Centre P&L, Partner-Manager P&L, and
Comparatives sheet SUMIFS references shifted to account for the
new column position (Amount F → G, CostCentre B → C).

**5. Client Billing: ``Grand Total`` column now SUM-formula driven.**
Each row's Grand Total is ``=SUM(<first period col>:<last period
col>)`` so the operator can tweak a cell and the total recalculates
live. Was a hard-coded value before.

Smoke test reproduces the operator's exact bug + verifies both
displayed-and-stored fixes:

    BEFORE: raw 'Bilimoria Mehta & Co' -> client 'Dinaz Mehta'
    AFTER : raw 'Bilimoria Mehta & Co' -> client 'Bilimoria Mehta & Co'

Generated Salary sheet now reads:
    Period | Date        | CostCentre | Employee | Client    | Hours | Amount
    2026-05| 03-May-2026 | AM         | Sahil    | Client A  | 4     |    806.45
    2026-05| 15-May-2026 | JV         | Sahil    | Client B  | 8     |  1,612.90
    2026-05|             | AM         | Sahil    | (residual)| 236   | 47,580.65

Generated Client Billing shows ``=SUM(C5:C5)`` in the Grand Total cell.

### v0.3.57 — Fixed office overhead + per-CC salary allocation + client billing
Three connected enhancements driven by the operator's salary-costing
workflow.

**1. New ``fixed_office_overhead`` master tab (migration v10).** Table
holds per-period (YYYY-MM) ``amount_per_employee``. Editable in
Master Data → Fixed Office Overhead. Management revises monthly.

**2. Salary cost allocation rewritten.** Old behaviour: per-employee
rate = ``salary_paid / actual_timesheet_hours``, so an under-filled
timesheet inflated the rate. New behaviour:

* Per (employee, period): ``total_cost = salary_paid + overhead``
  where ``overhead = fixed_office_overhead.amount_per_employee`` for
  that period.
* ``rate = total_cost / (days_in_month × 8)`` — uses the firm's
  standard month-hours, not actual logged hours. A 250-hour timesheet
  and a 12-hour timesheet now produce the same hourly rate.
* Each timesheet line books ``hours × rate`` against the client's
  cost centre.
* Any residual (``standard_hours − total_logged``) goes to the
  employee's home cost centre (``employees.default_cost_centre_id``,
  fallback to salary-row CC, fallback to Office) so the full monthly
  cost lands somewhere — no labour cost silently vanishes when a
  timesheet is sparse.

Worked example from the smoke test: Sahil's home is AM. May 2026 has
31 × 8 = 248 standard hours. Salary ₹50k + overhead ₹10k → rate
₹241.94/h. Timesheet: 100h Client ABC (AM) + 4h Client XYZ (JV) +
8h Client LMN (KS). Residual = 248-112 = 136h to AM.

  AM total: (100+136) × 241.94 = ₹57,096.77
  JV total:        4 × 241.94 = ₹  967.74
  KS total:        8 × 241.94 = ₹1,935.48
                                ─────────
  Sum:                          ₹60,000.00  ← matches salary+overhead

**3. Sheet renamed "Labour" → "Salary".** Every internal helper,
SUMIFS reference, sheet name, Cost Centre P&L column header
("Salary Cost"), and footnote updated. Comparatives sheet's prior-
period lookup updated too.

**4. New "Client Billing" sheet.** Client × period matrix mirroring
the operator's reference layout (``client wise biling.xlsx``):

    Client            | Grand Total |  May 26  |  Jun 26  |  …
    Client ABC        |     75,000  |   75,000 |          |  …
    TATA SONS PVT     |  1,01,80,000|  …       |  …       |  …

Sorted by Grand Total descending; final TOTAL row summed via formula.
Credit/Debit notes flow through with their signs so the net billing
nets returns automatically.

End-to-end smoke test: synthesized employee + 3 clients in 3 partner
cost centres + salary + overhead + revenue → all numbers reconcile
to the paise. Sheets present: ``Salary`` ✓, ``Labour`` absent ✓,
``Client Billing`` ✓. MasterDataPage constructs with the new
"Fixed Office Overhead" tab.

### v0.3.56 — Debit Notes: supplementary sales (+ve revenue), not purchase returns
Operator reported Debit Note entries booking to expenses as negative
figures, but in this firm's accounting practice Debit Notes are
**supplementary sales invoices** (additional bills raised on top of
the original Sales invoice to clients) — they must add to the
partner's revenue, not subtract from expenses.

v0.3.54 treated Debit Notes as the textbook "purchase return"
interpretation: ``kind='expense'``, sign=-1. Wrong for this firm.

Three coordinated changes — plus a data-fix migration so the live DB
gets corrected on first launch without a re-import:

**Sniffer**. ``Debit Note Register`` / ``Debit Note-D Register``
banners now route to ``kind='sales'`` (previously purchase).
Updated the comment block in ``sniffer.py`` so the next person
reading the code understands the firm-specific interpretation.

**Parser ``_vch_side_and_sign``**. ``Debit Note`` → ``('cr', +1)``
(was ``('cr', -1)``). Lines on the Credit column like a regular
Sales voucher, sign +1 so they add to the partner's revenue.
Credit Notes stay as ``('dr', -1)`` (sales returns reduce revenue).
7/7 unit tests pass.

**Migration v9**. Reclassifies any already-imported DN data in the
live DB:

* Snapshots vouchers where ``kind='expense' AND vch_type LIKE
  'Debit Note%'`` into a TEMP table,
* Flips ``voucher_splits.amount`` sign (``-X`` → ``+X``) on those
  vouchers' splits,
* Updates ``vouchers.kind`` from ``'expense'`` to ``'sales'``.

Snapshot-then-mutate so the two UPDATEs don't see each other's
effects. Idempotent — a second run finds zero expense-side DNs and
does nothing. Regular Purchase vouchers (control case in the smoke
test) untouched.

End-to-end verified: synthesized DB with two DN vouchers (one Mumbai,
one Delhi suffix) and a regular Purchase row. After v9 migration: DNs
flipped to ``sales`` + positive amounts, Purchase row untouched.
Idempotent re-run produces no further changes.

### v0.3.55 — "Clear all data" preserves every master table
Operator noticed that "Clear all data" was wiping the Clients and
Employees masters while leaving Entities, Cost Centres and Managers
intact. Asymmetric and surprising — those masters cost hours of
bulk-import + curation work and shouldn't disappear when the operator
just wants to redo a stale import.

Root cause: ``reset_all_data`` was deleting from **every** table
(``SELECT name FROM sqlite_master``), then calling ``_seed`` which
only re-seeds entities, cost centres, managers, and entity aliases.
Clients / employees / services / targets / saved CC-string mappings
/ column templates all got nuked with no restore.

Fix: inverted the logic. Reset now explicitly **wipes** only the
transactional / imported tables:

* ``import_batches``
* ``vouchers`` + ``voucher_splits``
* ``timesheet_entries``
* ``salary_entries``

Everything else — the entire Master Data UI plus saved CC-string
mappings, column templates, and app settings — is preserved. The
``_seed`` call after the wipe is now a no-op safety net for the
exceedingly rare half-broken DB case.

Updated the danger-zone copy + confirmation dialog so the operator
can see what stays vs. what goes before pressing the button.

Verified end-to-end: 13/13 master + config tables unchanged after
reset; 5/5 transactional tables wiped to zero.

### v0.3.54 — Credit/Debit Note registers + branch-suffixed banners
Operator reported two files broken:

* **BMCA delhi.xlsx** (banner ``Sales-D Register``) wasn't being read
  at all — sniffer returned ``kind=None``.
* **BMCA credit.xlsx** (banner ``Credit Note Register``) imported,
  but every credit-note ledger line came through as ``amount=0`` in
  the MIS — revenue silently dropped.

Two distinct bugs.

**1. Banner regex too literal.** v0.3.51's sniffer matched only the
fixed strings ``"sales register"`` / ``"credit note register"`` as
substrings. Tally's "-D" / "-BR" branch suffixes (Sales-D, Credit
Note-D, Purchase-D, Debit Note-D) broke the substring scan. Fix:
swapped both ``_BANNER_*`` constants for regexes that accept
``(?:[\\s-][\\w-]*)?`` between the type and "register". Now matches
"Sales-D Register", "Sales-BR Register", "Credit Note-D Register",
and so on. 11/11 banner test cases pass.

**2. Credit/Debit Notes have inverted sides in Tally.** A regular
Sales voucher books revenue on the Credit column with "Cr" CC tags;
a Credit Note (sales return) inverts this — ledger lines move to the
Debit column with "Dr" CC tags. Same flip for Debit Notes inside
a Purchase Register. The parser previously hard-coded
``revenue_col = cr_i`` for the whole sales file, so every credit-note
ledger line read as ``0`` from the Credit column and was silently
skipped. Verified: BMCA credit.xls's 46 credit notes had 0 lines
captured before this fix.

Fix:

* New helper ``_vch_side_and_sign(vch_type, file_kind)`` returns
  ``(side, sign)`` per voucher. Credit Note → ``('dr', -1)``;
  Debit Note → ``('cr', -1)``; ordinary Sales/Purchase keep the
  file-level defaults.
* ``parse_tally`` now picks side + sign **per voucher** off the
  ``Vch Type`` cell of each voucher header, not once for the whole
  file. Subsequent ledger lines + CC tags use the per-voucher side;
  amounts are multiplied by the sign so returns book negative.
* Net result: a ₹7,500 Credit Note for Vishal Kothari stores
  ``amount = -7500`` on the voucher split; the partner P&L's SUMIFS
  naturally nets it against gross sales. 11/11 side+sign unit tests
  pass.

Verified end-to-end on the two reported files:

    BMCA delhi.xlsx   sales  Bilimoria Mehta & Co.    3 vchs   net = +269,400.00
    BMCA credit.xlsx  sales  Bilimoria Mehta & Co.   46 vchs   net = -2,937,790.92

Credit-note line amounts now flow through to the MIS with the right
sign — partner totals will net correctly.

### v0.3.53 — End-to-end correctness on all 10 entity exports
Operator handed over 10 Tally exports covering every entity in the
firm (Bilimoria Mumbai, Bilimoria Bangalore, Corporate, MASD,
MASD Advisors, Qualzen) — both Sales and Purchase Registers — and
asked: does the system catch entity + voucher type correctly, and
do the totals come out right? Sweep uncovered three real bugs that
together would have caused silent revenue loss + entity misallocation.

**Bug 1 — Revenue silently classified as tax.** The ``is_tax_head``
heuristic used a substring scan with ``"gst "`` in its keyword list,
which flags any ledger whose name contains "GST" — including service
ledgers like ``GST Returns Filing Fees`` and ``GST Audit Fees``. In
the operator's Bilimoria Jan'26 file alone, this misclassified
₹1.17M of revenue (68/242 vouchers) as tax, silently zeroing them
out of the P&L. Fix: switched to a word-boundary regex matching
specific tax tokens (``\bcgst\b``, ``\btds\b``, ``\bround[-\s]?off\b``,
``output gst`` / ``input gst``). 19-case unit test covers the
revenue-vs-tax boundary.

**Bug 2 — Bangalore branch always mapped to Mumbai HQ.** Bilimoria's
Mumbai and Bangalore entities share the same legal name
(``Bilimoria Mehta & Co.``) — only the address line distinguishes
them. v0.3.51's entity matcher only read row 0 (the name), so BRL
files matched Mumbai every time. Fix:

* ``sniffer.detect_letterhead_text`` now returns the full
  letterhead block (name + address + contact), not just row 0.
* ``match_entity`` scans the letterhead for entity-alias hits and
  scores by (alias_hit_count, longest_alias_length). Aliases are
  the distinguishing signal — they're seeded explicitly for the
  ambiguous cases. Name matches are only a fallback when no
  aliases hit anywhere.
* Seed adds disambiguating aliases:
  - Bangalore: ``Bengaluru``, ``Bangalore``, ``Jayanagar``
  - Corporate: ``BMC Corporate Solutions Pvt Ltd``, ``BMC Corporate``
  - MASD: ``MASD ADVISORS PRIVATE LIMITED``, ``MASD & CO LLP``
  BRL letterhead now scores: entity 6 with 2 alias hits
  (``Bengaluru``, ``Jayanagar``) > entity 1 with 1 hit
  (``Bilimoria``) → Bangalore wins correctly.

**Bug 3 — Migration v8 ran before its data existed.** Initial fix
put the new aliases in migration v8, but the migration runs BEFORE
``_seed`` populates the entities table — every ``INSERT INTO
entity_aliases SELECT id FROM entities WHERE name=…`` returned
zero rows. Moved the seed of these aliases into ``_seed`` (where
entities are already in place) alongside the original ``Bilimoria``
/ ``Corporate`` / ``Advisors`` short forms.

End-to-end verification on the operator's 10 real exports:

    OK Advisor Purchase Jan 26.xls         MASD Advisors          1,818,000 / 1,818,000
    OK Advisor Sale Jan 26.xls             MASD Advisors            646,282 /   646,282
    OK BRL Purchase Jan 26.xls             Bilimoria … (Bangalore)   92,536 /    92,536
    OK BRL Sale Jan 26.xls                 Bilimoria … (Bangalore)   55,400 /    55,400
    OK Bilimoria Sale 2026.xls             Bilimoria Mehta & Co. 17,859,438 / 17,859,438
    OK Bilomoria Purchase Jan 26.xls       Bilimoria Mehta & Co.  3,190,899 /  3,190,899
    OK Corporate Purchase Jan 26.xls       BM Corporate             377,800 /   377,800
    OK Corporate Sale Jan 26.xls           BM Corporate             697,823 /   697,823
    OK MASD Purchase Jan 26.xls            MASD & CO              1,450,430 /  1,450,430
    OK Qualzen Sale Jan 26.xls             Qualzen                   50,000 /    50,000

All 10: correct kind, correct entity, parsed gross == Tally
bottom-row total to the paise.

### v0.3.52 — Bulk employee master import + fuzzy-link unresolved
Operator dropped an EmployeeData Excel (125 rows of name + cost-centre
code) and asked: load this into the master, and clean up the
salary/timesheet rows that are still sitting in the unresolved queue.

Mirrors the v0.3.50 client-import pattern:

* New service ``bulk_import_employees(pairs)`` — case-insensitive
  CC-code lookup, fills NULL ``default_cost_centre_id`` on existing
  rows, inserts new employees for missing names, reports unknown
  codes. After the upsert, runs the fuzzy-link pass automatically.
* ``_fuzzy_link_employees`` — for every distinct raw name in
  ``salary_entries.employee_name`` and ``timesheet_entries.emp_name``
  that doesn't exact-match an employee or alias, score against active
  employees by ``token_sort_ratio``; if the top score is ≥70 AND ≥5
  points clear of the runner-up, write a ``source='fuzzy'`` row to
  ``employee_aliases``. Re-imports of the same raw name then hit the
  cheap exact path.
* ``apply_known_employee_aliases`` (was a no-op) now drives the
  fuzzy pass, so the same resolution happens automatically after
  any import.
* New 📁 Import-from-Excel button on Master Data → Employees;
  shares the ``_import_name_cc_pairs_from_excel`` helper with the
  v0.3.50 clients flow.

Verified end-to-end on the operator's real EmployeeData file:
125 employees created, 0 unknowns; 3 of 6 pre-existing salary
rows resolved via exact-norm (case + whitespace), 2 via fuzzy
(``Harjeet Singh`` → ``Harjeet Arjun Singh``; ``Pranali P Gurav``
→ ``Pranali Pravin Gurav``), 1 truly-unknown name correctly held
for review.

### v0.3.51 — Auto-detect file type + entity from Tally exports
Two operator asks bundled.

**1. Backfill the 10-manager master into existing databases.**
v0.3.49 added the full manager list to ``_first_run_seed`` — that only
fires on a fresh install. Migration **v7** does the same idempotent
insert (INSERT OR IGNORE on the compound ``code``) on every existing
DB on next launch. Verified that re-running ``init_db`` after a fresh
init leaves the count at 10 (idempotent).

**2. Auto-detect file type + entity from Tally registers; reduce
the file-type dropdown to just Timesheet and Salary.**

Tally exports always carry a recognisable letterhead:

    Bilimoria Mehta & Co.
    <address lines>
    Sales Register     ← banner row
    1-Jun-26 to 30-Jun-26

So:

- ``sniffer.detect_kind`` now recognises Credit Note Register +
  Debit Note Register banners (mapped to sales / purchase
  respectively — returns ride on the same kind as the parent).
- New ``sniffer.detect_entity_name`` walks the top 8 rows for the
  company name, skipping numeric/address lines.
- New ``resolution.match_entity`` resolves a raw entity name to an
  entity id (exact → alias → fuzzy ≥70% with 5-pt gap). Conservative
  fallback to ``None`` when uncertain.
- ImportPage's file-type dropdown now lists only ``Timesheet`` and
  ``Salary & Reimbursements`` — the auto-detectable kinds aren't
  user-pickable. After picking a file, if the sniffer recognises a
  Tally banner, the page sets the internal kind from the banner AND
  auto-selects the entity dropdown from the letterhead. Status line
  shows what was detected, e.g.
  ``Detected: Sales register · entity: Bilimoria Mehta & Co.``

Verified on the operator's real BMCA file: kind='sales', entity
'Bilimoria Mehta & Co.' both detected, header row 6 found,
ImportPage constructs with the 2-option dropdown.

### v0.3.50 — Bulk client master import + fuzzy auto-link
Three asks in one release:

**1. Bulk-import the firm's client → cost-centre master from Excel.**
New button on Master Data → Clients: "📁 Import from Excel…" picks an
Excel with ``Client | Cost Centre`` columns (case-insensitive header
detection), looks each CC up by code in the cost_centres master, and
upserts. Existing clients with a NULL cost_centre get filled in;
existing clients whose cost_centre already matches are left alone;
rows with unknown CC codes are reported. Verified on the operator's
real 986-row dump: 986 created, 0 unknowns. The corresponding service
``resolution.bulk_import_clients`` is callable from code too.

**2. Walk back the client.manager_id field added in v0.3.47.** The
Sales/Purchase Register Excel now carries the manager-partner string
per voucher line (v0.3.49 matcher resolves both orderings), so a
default manager on the client master is redundant. The DB column
remains (migrations only add) but the field is no longer shown in
the Master Data → Clients tab, no longer surfaced in the
ResolveClientDialog, and ``apply_client_master_to_splits`` only
propagates cost_centre_id now — not manager_id.

**3. Fuzzy auto-link new party names against the client master.**
``apply_known_client_aliases`` now runs an exact-match pass followed
by a fuzzy pass at ≥70% with a 5-point gap requirement vs. the
runner-up. So ``PROCAM INTERNATIONAL PVT LTD`` → ``PROCAM
INTERNATIONAL PVT. LTD`` (95%) auto-links; ``Kensho Coffee LLP.`` →
``Kensho Coffee LLP`` (92%) auto-links; ``Procam International Pvt
Bangalore`` — ambiguous against 3+ Procam entries — stays unlinked
for the operator's review queue. Each fuzzy auto-link writes a row
to ``client_aliases`` so re-imports hit the cheap exact path.

### v0.3.49 — Smart manager-partner matching + full manager seed
Operator asked for two things:

1. Commit the firm's full 10-manager master to the seed (was 4 starter
   rows). Now seeds all 10 with compound codes (RM - PM, SR - AM,
   UV - AM, GS - KS, BS - SD, GS - AM, BS - JV, KS - SD, HD - JV,
   RR - VK) and each row wired to its partner via cost_centre_id.
   Note: this only takes effect on fresh installs; the operator's
   existing DB already holds the same records from manual entry.

2. CC strings of the form "X - Y" should resolve correctly regardless
   of order — "Shreyans - Bhavya" / "Bhavya - Shreyans" both → BS - SD;
   "Aakash - Sahil" / "Sahil - Aakash" both → SR - AM — and ambiguous
   manager names should be disambiguated by the partner context, not
   silently guessed.

The matcher's "X - Y" logic already tried both orderings and worked
for the 14 non-ambiguous test cases. The one real bug: when the same
manager name appears under multiple partners (Gaurav Siroya is under
both Aakash Mehta and Kiran Suvarna), the global manager_lookup
silently picked one based on dict-insertion order — so "Kiran - Gaurav"
returned GS-AM instead of GS-KS.

Fix: ``_build_partner_manager_lookups`` now also returns a
``managers_by_partner`` dict — one lookup per partner cost-centre,
holding only that partner's team. When the partner side of an
"X - Y" string is resolved first, the manager search uses the
partner-scoped lookup before the global one. Inside a single
partner's team, "Gaurav" is unambiguous, so the right role
(GS - KS or GS - AM) gets picked. Ambiguity that remains after
the partner constraint still bubbles up to the operator's review
queue — no silent guesses.

Verified: 17 / 17 test cases pass (including both orderings of every
name pair); the 4 real-world CC strings in the operator's actual
sales register continue to resolve at score=100.

### v0.3.48 — Reframe Import page: Excel is the primary path
Operator asked for an "overhaul" so the Sales Register Excel from Tally
gets parsed end-to-end with per-line cost-centre / manager attribution
(multi-service vouchers each split with their own CC). Investigation
showed the parser ``parsers.parse_tally`` already produces exactly that
shape — verified on the operator's actual BMCA Excel: 19 vouchers,
correct per-line splits, multi-service vouchers (Velox CERTIFICATION
+ AUDIT) split into separate lines with the same CC each, tax lines
flagged ``is_tax=True`` and rolled into voucher tax_amount.

The actual problem was UX framing. The Import page presented the
Tally HTTP pull as "Primary path" and the Excel upload as "Fallback",
which sent the operator down the HTTP path. On their Tally install
the HTTP gateway returns empty ``CATEGORYALLOCATIONS.LIST`` elements
(verified via the diagnostic XML) — so the HTTP path can never
populate cost centres for this operator's setup, while the Excel
export from the same Tally UI does.

Change: swapped the framing — Excel upload moved to the top of the
page and labelled "Upload an Excel file (recommended)"; Tally HTTP
pull moved below as a secondary option for installs whose gateway
exposes per-line cost centres. Note text updated to explain the
trade-off.

No parser changes. No schema changes.

### v0.3.47 — Manager field on client master (+ fallback to splits)
Operator request: bind each client to a default Manager too, not just
a Cost Centre (partner) — same shape as ``cc_string_mappings``. Critical
when a firm's Tally doesn't tag cost centres on voucher lines: every
split is unassigned, the cc-string mapping has nothing to bite on, and
the client master becomes the only path to populate the Partner-Manager
P&L.

Changes:
- DB migration v6: ``ALTER TABLE clients ADD COLUMN manager_id``.
- Master Data → Clients tab: new ``Manager`` column / form field.
- Resolve-Client dialog (new-client flow): Manager dropdown alongside
  Cost Centre.
- ``resolution.create_client`` accepts ``manager_id``.
- New ``apply_client_master_to_splits()`` — pushes each client's
  cost_centre_id and manager_id down to its vouchers' splits when
  those splits are NULL. Cc-string mappings still win when present.
  Wired into ``infer_all_masters()`` so it runs after every operator
  action and every import.

### v0.3.46 — Expense vouchers also resolve against client master
The new Client column on the Expenses sheet (v0.3.45) was always showing
"(unmapped)" because the client-resolution code was gated on
``kind='sales'`` everywhere — meaning expense vouchers' party names were
captured but never matched against the client master / aliases.

Dropped the ``kind='sales'`` filter from ``_apply_client_norm_mapping``
so existing client masters & aliases now apply to expense vouchers too.
Most expense parties are vendors (banks, landlords, consultants) and
won't match anything — they stay unmapped, which is correct. But when
an expense voucher's party *is* a known client (journals or credit
notes raised against a client, reimbursements recorded as receipts),
the Client column on the generated MIS now shows the real name.

Did NOT extend the filter on ``unresolved_clients()`` — keeping that
sales-only avoids flooding the operator's review list with every
vendor name in Tally.

### v0.3.45 — Client column on Expenses sheet
Operator requested a ``Client`` column on the generated MIS's Expenses
data sheet (mirrors the existing Client column on Revenue). Added after
Service, before Amount. The expense fact dict already carried
``client_id`` from ``vouchers.client_id`` — only the sheet writer needed
to render it. Shifted Amount G→H and Description H→I, and updated every
downstream SUMIFS that referenced the old expense Amount column:
Cost Centre P&L direct-expense cell, Partner-Manager P&L expense row,
Entity / Service summaries, and the Comparatives sheet's prior-period
expense lookup.

### v0.3.44 — Enhanced diagnostic CSV (full visibility)
User's v0.3.43 diagnostic CSV came back **empty** — meaning
``unresolved_cc_strings()`` had no rows. Combined with their earlier
screenshot of "63/63 vouchers needs fix", this is the smoking gun:
the CC names aren't being **extracted** from the Tally XML at all,
so there's nothing in the database for the matcher to work with.

Rebuilt the diagnostic CSV to show the full picture — three sections:

1. **Summary row** at the top: total splits / resolved /
   unresolved-with-raw / unresolved-WITHOUT-raw. That last column is
   the smoking gun for an XML-extraction problem.
2. **Matcher diagnosis** of unresolved-with-raw rows (existing behaviour).
3. **Sample of vouchers with no raw CC at all** (top 20 by date) —
   shows ``vch_no``, ``vch_type``, ``party_name``, ``ledger_head`` so
   the operator can verify in Tally whether those specific invoices
   actually have cost-centre tags assigned.

If section 3 dominates, the issue is XML extraction → operator
shares ``tally_last_response.xml`` from the data dir and we patch.
If section 2 dominates, it's a matcher gap → we patch the matcher.

### v0.3.43 — Broader tokenizer + CSV diagnostic export
User confirmed it's a matcher issue. v0.3.39 added token-level exact
matching but only split on whitespace, missing the bulk of real-world
operator-customised CC strings that use punctuation as separators.

- **`_tokenize` helper** (used by ``_best_match``) now splits on
  whitespace **plus** every common separator: ``_``, ``.``, ``,``,
  ``;``, ``:``, ``|``, ``()``, ``[]``, ``/``, ``-`` (all dash variants),
  ``&``. Also splits at alpha/digit transitions so ``VK2026`` → ``vk``
  + ``2026``. The partner code or singleton name buried in the
  string surfaces as an exact token match.
- **Honorific regex** loosened to handle missing space after the dot
  (``Mr.Vishal Kothari`` works now, not just ``Mr. Vishal Kothari``).
- **New "📋 Export diagnostic" button** on the CC Strings tab writes
  a CSV with: every unresolved string + its normalised form + the
  tokens we extracted + saved-mapping partner + suggested partner +
  confidence score + a one-line diagnosis ("HAS MAPPING but split
  unresolved — BUG", "matcher would resolve at X%", "low confidence",
  "no plausible partner"). Lets the operator share concrete data
  with the developer for any stubborn cases.

Verified across 23 patterns — all 13 previously-failing variants
(underscores, dots, commas, parens, brackets, pipes, semicolons,
colons, ampersands, alpha-digit boundaries) now resolve to the right
partner; ambiguous and unrelated strings still correctly abstain.

### v0.3.42 — Defensive CC extraction + clear "Tally has no CC tags" warning
User screenshots showed 63/63 vouchers with "needs fix" status and 45
unmapped clients — far too many for a matcher issue. Inspection
revealed the more likely cause: **the cost-centre data wasn't being
extracted from Tally's XML at all** for this operator's data. If the
raw text is empty, no amount of matcher tuning helps.

- **More defensive ``_ledger_cost_centre``**: tries every Tally XML
  variant we've seen in the wild — ``<CATEGORYALLOCATIONS.LIST>`` +
  ``<COSTCENTREALLOCATIONS.LIST>`` (Tally Prime standard); the flat
  form; the no-``.LIST`` form (``<COSTCENTREALLOCATIONS>``); the
  ``<COSTCENTRES>`` form. CC name can be in a ``<NAME>`` child, a
  ``<COSTCENTRENAME>`` child, **or** a ``NAME="…"`` attribute. Final
  fallback walks every descendant looking for any of those wrappers
  in case the structure is unexpectedly nested.
- **New diagnostic warning** appended to the parse result whenever
  fewer than 100% of revenue lines have a cost-centre tag:
  > "Cost-centre tags on 8/63 revenue lines (12%) — 55 line(s)
  > have NO cost centre in Tally. Those vouchers will show
  > 'needs fix' in Review (the matcher can't help when Tally
  > hasn't tagged the partner). Confirm cost centres are enabled
  > in Tally and the operator selected one when entering the
  > voucher."

  Surfaces in the pull result panel, making the difference between
  "we can't extract" and "Tally doesn't have it" visible at a glance.
- Verified across 5 structural variants — 4 known layouts all
  extract correctly; the "no CC at all" case correctly triggers the
  diagnostic warning.

### v0.3.41 — Pull-result diagnostic for unresolved CC strings
User: "the system is still not picking up the cost centres from tally
import" but explicitly thought it wasn't a threshold issue. Rather than
guess at the cause, surface concrete diagnostic info inline so the
actual gap is visible.

- **New `resolution.diagnose_unresolved_cc(limit)`** returns
  ``{raw, count, suggested_partner, score}`` for the top-N unresolved
  CC strings, computing the matcher's suggestion at threshold 50
  (deliberately low so weak matches still appear).
- **Pull result panel** now lists those entries inline with one of
  three colour-coded markers:
  - **🔴 Red** "⚠ should auto-resolve to <b>VK</b> (100%)" — score
    ≥ 65 but still unresolved. **This is a bug** — the apply path
    didn't fire, the user shares it and we patch.
  - **🟡 Yellow** "suggests <b>VK</b> (62%) — click Confirm suggested
    in Review" — borderline match, operator confirms in one click.
  - **⚪ Gray** "no suggestion — operator picks manually" — truly
    unknown / ambiguous (operator-specific strings, "Mehta" alone,
    "Recovery Account" etc.). Expected behaviour.
- Lets the operator immediately see what kind of issue they're
  looking at, and gives us a precise list of strings to teach the
  matcher about if the gap is in our logic.

### v0.3.40 — Dedupe ledger entries within a voucher (forex double-count fix)
Field-test feedback: foreign-currency vouchers were being counted twice
in the partner P&L. Tally occasionally emits the same revenue ledger
line twice in the XML for forex vouchers — once with the formatted
``$ 1000 @ 80/Re = 80000`` notation and once with the plain INR after
settlement. Our walker processed both → revenue doubled.

- **`_voucher_from_xml`** now de-duplicates ledger entries inside each
  voucher by ``(ledger name, |amount|, cost-centre name)``. A genuine
  forex double-emission is squashed; legitimate multi-line vouchers
  (different ledgers, different CCs, or same ledger split across
  partners) all stay intact.
- Verified across three scenarios — forex duplicate squashes from
  2 splits to 1 (₹80K, not ₹160K); a normal multi-service voucher
  with FEES + AUDIT FEES + GST keeps 3 splits; a multi-CC split of
  the same ledger to two partners keeps 2 splits.

### v0.3.39 — Pre-fill Resolve dialog + Confirm-suggested bulk + smarter match
User feedback: "the system is still not taking the cost centres from the
tally import, it is still showing to resolve it". Real strings like
``Vishal Audit`` weren't auto-resolving despite "vishal" being a clear
partner singleton — the short partner code ``"al"`` was matching
``"audit"`` at partial_ratio 100, creating a tie with ``"vishal"`` so
the matcher abstained.

**Smarter matching** (``_best_match`` rewrite):
- **Token-level exact match** added as a second pass: each whitespace-
  separated token of the query is checked against the lookup. Catches
  ``VK Audit 2026`` → VK, ``Vishal Audit`` → VK, ``PM Tax`` → PM, etc.,
  without any fuzzy scoring at all.
- **Short keys excluded from fuzzy partial-ratio**. Codes like ``VK``,
  ``PM``, ``AL`` stay in the lookup for exact / token-level matching
  but are dropped from the fuzzy pool (length ≥ 4) so they can't
  generate false positives against unrelated text (``"audit"`` contains
  ``"al"``; ``"random"`` contains ``"ran"`` matching ``"kiran"``).
- **Partial-ratio gated at 85+**. token_sort_ratio runs full-range
  (it's more conservative); partial_ratio only contributes when it
  scores 85+, so loose substring overlaps don't bleed into suggestions.
- Auto-match threshold lowered to 65 (from 70) now that the matcher
  is tighter — picks up more real matches without false positives.

**UI**:
- **ResolveCcStringDialog** now pre-fills the partner + manager combos
  from ``suggest_for_raw_cc`` (threshold 50). Operator opens the
  dialog and the suggested partner is already highlighted; they just
  hit Save. A green hint shows the confidence percentage.
- **CC Strings tab** got a new **"Suggested partner"** column showing
  the matcher's guess inline (e.g. ``VK — Vishal Kothari  +  mgr SR
  (87%)``). No more opening each Resolve dialog to see what the
  system thinks.
- **"✓ Confirm suggested" bulk button** at the top of the CC Strings
  tab applies every row's suggested mapping in one click. The
  mappings get saved to ``cc_string_mappings`` so future imports of
  the same string auto-resolve.

**Verified across 28 inputs** — full names, codes, first names, last
names, partner-manager combos, compound words ("VKothari"),
multi-word strings ("Vishal Audit", "VK Audit 2026"), ambiguous
queries ("Mehta"), and false-positive baits ("Random Unknown",
"Random Test"). 27 / 28 perfect; the only "fail" is a legitimately
weak 50% match that surfaces as a low-confidence suggestion the
operator can override (and won't get auto-applied).

### v0.3.38 — Date + Voucher No on data sheets; looser voucher-type regex
Three asks from the user, one bundle:

- **Revenue + Expenses data sheets** now have ``Date`` (actual
  transaction date, formatted ``05-Jun-2026``) replacing the old
  ``Period`` column, and a new ``Voucher No`` column right after it.
  Lets the operator drill into a partner's revenue line and trace
  it back to the specific Tally invoice.
- **Calc** loads ``v.txn_date`` and ``v.vch_no`` alongside the
  existing fields so both data sheets can populate them.
- **All SUMIFS references** shifted to the new column layout — Cost
  Centre P&L, Partner-Manager P&L (with the inner ``sumifs`` helper
  re-anchored to columns D/E), Entity P&L, Service MIS, and
  Comparatives. Verified with a generated workbook against the
  expected ``$H:$H`` / ``$D:$D`` / ``$E:$E`` / ``$I:$I`` columns.
- **Debit Note regex made tolerant** of any of space / hyphen /
  slash / dot between "debit" and "note" so user-created variants
  like ``Debit-Note`` or ``Debit.Note`` are picked up as expense
  returns. Same loosening applied to ``Credit Note``, ``Sales
  Return``, and ``Purchase Return``.
- **New diagnostic** appended to the parse result warnings: every
  voucher type we *didn't* classify is listed with its count
  ("Skipped 47 non-revenue voucher(s): Receipt=20, Payment=15,
  Journal=12") and shown in the pull result panel. Lets the
  operator see exactly which voucher types Tally returned that we
  silently dropped — if any of them are actually revenue/expense
  types we should support, they can share the name and we'll add
  it to the classifier.

### v0.3.37 — Credit Notes + Debit Notes (sales/purchase returns)
Operator's books include credit and debit notes — sales / purchase
returns and billing adjustments — that previously got silently
dropped because v0.3.33 only matched ``Sales`` / ``Purchase`` prefixes.
Now picked up automatically, with the right sign so they reduce
revenue / expense in the MIS.

- **``_classify_vch_type`` now returns ``(kind, is_return)``** instead
  of just ``kind``. New regexes handle:
  - ``Credit Note``, ``Credit Note D``, ``Credit Note - Delhi``,
    ``CreditNote`` → ``(sales, True)`` — reduces revenue
  - ``Debit Note``, ``Debit Note D``, ``Debit Note/Mumbai`` →
    ``(expense, True)`` — reduces expense
  - Legacy ``Sales Return`` / ``Purchase Return`` also map to the
    same return classification
- **Parser flips the item side** for returns: a credit note's
  revenue line lives on the Debit side (reversing the original
  Credit). The walker now picks the right side based on
  ``(kind, is_return)``.
- **Amounts stored NEGATIVE** for returns (``sign_mult = -1``).
  Every ``SUMIFS`` in the MIS workbook naturally subtracts them, so
  partner-level revenue / expense totals come out correct without
  any per-row flag or formula changes downstream.
- Dedup, CC auto-match, services auto-create, MIS generation all
  work unchanged — only the sign of the stored amount differs.
- Verified end-to-end: a Sales voucher of ₹10,000 + a Credit Note
  of ₹3,000 for the same partner correctly nets to ₹7,000 in the
  partner P&L. 18 / 19 voucher-type classifications correct
  (the only "failure" was a too-strict test expectation).

### v0.3.36 — Pre-fill Cost Centre on resolve dialogs + tighter fuzzy
Reduces the operator's per-voucher click count: the Resolve Client
dialog already pre-fills "Cost centre" from prior splits; the new
``suggest_for_raw_cc`` helper now also pre-fills the Split Editor's
partner + manager dropdowns based on the raw Tally CC text on each
split. Operator opens an unmapped voucher and clicks Save — done.

- **New `resolution.suggest_for_raw_cc(raw)`** returns
  ``(partner_cc_id, manager_id, confidence)``. Looks up saved
  mappings first; falls back to fuzzy matching with a tightened
  pipeline (see below). UI uses it to pre-fill the Split Editor.
- **`suggest_cc_for_raw_client`** extended: when no split has a
  resolved ``cost_centre_id`` yet (common on a fresh Tally pull
  before review), falls back to the dominant ``raw_cost_centre``
  text on those splits and runs it through
  ``suggest_for_raw_cc``. Pre-fills the new-client dialog from
  Tally's own CC tag.
- **`SplitEditorDialog._add_row`** now pre-fills the CC and Manager
  combos for any row where ``cost_centre_id`` is NULL but
  ``raw_cost_centre`` is set. Italic + tooltip ("Suggested from
  Tally CC ...") flags the row as a pre-fill the operator should
  confirm. Also auto-populates the Note column with the raw Tally
  CC so it's visible alongside the dropdowns.
- **Fuzzy matching tightened** to keep pre-fills accurate:
  - Suggest threshold raised to 80 (auto-match stays at 70).
  - Singleton-name keys (length ≥ 4) only added when *unambiguous*
    across the master — "Vishal" → VK (only Vishal), but "Mehta"
    no longer maps to PM because it's shared across PM / AM / MS.
  - ``_best_match`` now detects **score ties**: if multiple master
    entries tie for the top score and map to different ids, it
    abstains. "Mehta" → no suggestion (correct); "Mr. Prakash
    Mehta" → PM (correct, unambiguous full name).
- Verified across 19 inputs — clean pass: full names, codes, first
  names, last names, partner-manager combos, ambiguous strings
  (Mehta / Mehtaa), random-text false positives all behave correctly.

### v0.3.35 — Explicit Tally company dropdown (no more auto-detect surprises)
v0.3.34 made the pull use Tally's "current company" — but if the
operator has multiple companies open (and the wrong one happens to be
in focus, sometimes a background instance with no visible window), the
auto-detect still picked the wrong company. The fix: stop guessing,
let the operator pick.

- **New editable dropdown** on the Pull-from-Tally section. After
  clicking Test, it lists every company Tally knows about (current
  + the rest of ``list_companies``). The operator picks one
  explicitly; that exact name goes through as ``SVCURRENTCOMPANY`` on
  the pull request so Tally is *forced* to use that company,
  regardless of which one is in focus.
- **Free-text override** — the dropdown is editable, so if
  ``list_companies`` returns nothing or omits the company they want,
  they can type the exact name (must match Tally's company name
  character-for-character).
- **_ProbeWorker** now bundles the ``current_company`` + 
  ``list_companies`` queries so the dropdown gets populated in one
  round-trip on Test.
- **Status line** shows ``current: <name>`` plus the count of other
  loaded companies, so the operator can spot a multi-company state
  at a glance.
- **_PullWorker** no longer probes Tally first — it uses the
  dropdown's text verbatim. Pull is now 100% deterministic: what's in
  the box is what Tally is asked for.

### v0.3.34 — Lock pulls to a specific Tally company + mismatch warning
Field-test exposed the "multiple companies open in Tally" footgun.
Operator had MSIPL loaded in Tally and Bilimoria selected as the
target entity in our app — yesterday's pull happened to be Bilimoria
(250 vouchers), today's came back with 14 (MSIPL's vouchers) because
Tally returned data for whichever company was *in focus* rather than
the one we wanted.

Fixes:

- ``_PullWorker`` now probes Tally's current company first and passes
  the name as ``SVCURRENTCOMPANY`` on the Day Book request. Tally
  returns data for that exact company, not whichever one happens to
  be in focus.
- **Result label always shows** ``"Pulled from <company> — N voucher(s)
  in range"`` so the operator can see at a glance which Tally company
  contributed the data.
- **Mismatch confirmation dialog**: if the operator picks an entity
  explicitly (e.g. Bilimoria) but Tally has a *different* company
  loaded (MSIPL), we show a Yes/No dialog asking whether to proceed —
  prevents wrong-company data from being committed silently under the
  right entity_id.
- **Entity matching is now suffix-tolerant**: Tally Prime returns
  split-period company names like ``"Bilimoria Mehta & Co. - (From
  1-Apr-2011) - (from 1-Apr-2016)"``; ``_entity_id_for`` now matches
  those against the master entity ``"Bilimoria Mehta & Co."`` via a
  contains / prefix check.
- "No vouchers found" warning also surfaces which company was queried,
  so the operator can spot a wrong-company state immediately.

### v0.3.33 — Forex vouchers + custom voucher types + lenient CC match
Second batch of live-pull feedback: forex (USD/EUR) invoices were
skipped, custom voucher types like "Sales - Delhi" weren't picked up,
and many vouchers landed in Review with "needs fix" status.

- **Forex amounts now parse.** Tally's AMOUNT field for foreign-currency
  vouchers comes as ``$ 1000.00 @ 80.00/Re = -80000.00``. ``float()``
  rejected that, so the line was given amount=0 and the voucher was
  dropped. ``_parse_amount`` now handles three shapes:
  - plain decimal (existing behaviour)
  - forex with ``=``: take the INR value after the last ``=``
  - forex without ``=``: pick the largest-magnitude number (INR is
    almost always larger than the foreign value)
- **Voucher type prefix matching.** Operators routinely create
  ``Sales - Delhi``, ``Sales - Export``, ``Sales Mumbai``, ``Purchase
  Imports`` etc. — the old code only matched ``Sales`` / ``Purchase``
  exactly. New ``_classify_vch_type`` matches via prefix (followed by
  space, hyphen, slash or end-of-string), so all of those land
  correctly. Sales Return / Purchase Return are intentionally excluded
  (Credit Note / Debit Note class — inverse sign semantics not yet
  modelled).
- **Dropped the TDL FILTER.** Tally formula language varies across
  Prime / ERP 9 builds and a wrong filter silently drops every match.
  Now we fetch all vouchers in the date range and filter by type in
  Python via ``_classify_vch_type``. Bandwidth cost (a few KB of
  receipts / payments / journals per pull) is negligible.
- **More lenient CC auto-match.** Lowered ``_MIN_SCORE`` from 80 to
  70 (partners are a fixed set of 8 — fuzzy errors are unlikely); also
  added partner *code* and *first / last name* singletons to the
  lookup so Tally CC strings like ``VK``, ``Vishal``, or ``Kothari``
  all hit the right partner without operator intervention. Manager
  matching gained the same treatment.
- **NAME_SEP regex** now also splits on ``/`` so ``"Vishal / Audit"``
  patterns work.
- Verified end-to-end with 3 synthetic Tally responses: USD invoice,
  Sales-Delhi voucher, Sales-Mumbai voucher with first-name-only CC.
  All commit cleanly, all splits resolve to VK partner, Review
  reports "all vouchers resolved cleanly".

### v0.3.32 — Sanitize undeclared namespaces + bare ampersands
Next live pull crashed with ``unbound prefix: line 356, column 6`` —
Tally Prime emitted a namespaced tag (``<udf:UserField>`` or similar)
without declaring the ``udf`` namespace, which expat refuses. Same
pattern as the earlier control-character issue: Tally writes
technically-malformed XML and the strict parser rejects it.

Extended ``_sanitize_xml_bytes`` to also handle:

- **Undeclared namespace prefixes**: strips ``xmlns:foo="…"``
  declarations and rewrites ``<prefix:tag>`` / ``prefix:attr="…"``
  back to plain ``<tag>`` / ``attr="…"``. We don't read any
  namespaced fields, so dropping them is safe.
- **Bare ampersands**: Tally occasionally writes ``M&S Co`` or
  ``FEES & RECOVERIES`` without escaping the ``&``. We replace any
  ``&`` not starting a valid XML entity (``&amp;``, ``&lt;``,
  ``&gt;``, ``&quot;``, ``&apos;`` or a numeric ref) with
  ``&amp;``.

Verified across 4 problematic input shapes — namespaced tag, multi-
namespace doc, bare ampersand in party / ledger names, and a
combined-chaos case — all parse cleanly. Vanilla ``ET.fromstring``
crashes on 3 of the 4 without the fix.

### v0.3.31 — Pull every voucher in range + auto-refresh Review
Field-test feedback on the live Tally integration surfaced two issues:

- **Day Book ignored our date filter.** Tally's built-in "Day Book"
  report has a long-standing quirk where the XML export only returns the
  records currently in view in Tally's UI — so a 30-day request came
  back with just 3 vouchers, regardless of the date range we asked for.
  Replaced the request with a **Voucher Collection fetch**: a TDL
  `<COLLECTION>` of `Voucher` objects filtered by `(VoucherTypeName=Sales
  OR Purchase)`. Tally now returns every matching voucher in the range,
  independent of UI state. The cost-centre allocations come through
  automatically because the FETCH spec walks down `AllLedgerEntries.`
  `CategoryAllocations.CostCentreAllocations.Name`. Kept the old
  `envelope_day_book` name as an alias so callers don't break.
- **Imported vouchers didn't appear on Review until re-navigation.** The
  Review page reloaded only on its own `showEvent`. Added an `imported`
  signal on `ImportPage` (re-emitted from both the Tally pull and the
  Excel commit), connected at the MainWindow level to a new
  `ReviewPage.refresh()` method. Every successful pull / commit now
  refreshes Clients / Employees / Cost Centres / Vouchers tabs without
  the operator needing to switch pages.
- **Always-on response logging.** Every Tally pull now writes the raw
  XML response to `<data dir>/tally_last_response.xml` (overwritten on
  each pull). Lets us diagnose anything weird in the field without
  re-running the pipeline blind.

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
