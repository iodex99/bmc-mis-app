# Automated MIS Generator — Bilimoria Mehta & Co.

> Living document. Updated as we discuss. Last updated: 2026-05-22

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
- **2026-05-22** — Reporting period = **calendar month**; every row is
  bucketed by its actual date regardless of the file's label.
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
