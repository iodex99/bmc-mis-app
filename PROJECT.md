# Automated MIS Generator — Bilimoria Mehta & Co.

> Living document. Updated as we discuss. Last updated: 2026-08-18
>
> Current version: **v0.3.123** ([release history on GitHub](https://github.com/iodex99/bmc-mis-app/releases))

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
- **2026-07-13** (v0.3.105) — **Reimbursements use the firm's 21st →
  20th cycle too**, same as the timesheet. A reimbursement row's
  transaction date drives the bucket: dated 25 Apr → **May MIS**
  (May's window is 21 Apr → 20 May). Rows without a transaction date
  (pivot imports, manual entries) stay on their stated calendar month.
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

### v0.3.123 — Salary and Reimbursements are one sheet each ((FY) editions merged in)

Operator ask, the same one that produced v0.3.118 for Revenue / Expenses:
**"Salary (FY)"** and **"Reimbursements (FY)"** are gone. Their rows now
sit on the main **Salary** and **Reimbursements** sheets, the FY-prior
months first and the selected period's after them, told apart by a
trailing **Scope** column — one continuous register per kind instead of
hopping between two sheets.

* Scope lands at **O** on Salary (A..N data) and **K** on Reimbursements
  (A..J data). Appending it at the END means every column letter the
  formulas already name — Amount=I, Type=J, Billable=K, Manager=L, Pool
  Source=M on Salary; Amount=I, Employee CC=E on Reimbursements — stays
  exactly where it was.
* Every partner-level SUMIFS over the two sheets now carries the matching
  Scope criterion, built by the existing ``_scope_crit`` helper: the Cost
  Centre P&L, the Partner-Manager P&L (both its selected-period and
  FY-so-far columns) and ``_pm_leaf_formula``. Without it the
  selected-period figures would have quietly absorbed the earlier months.
  The current-window criterion stays ``<>FY Prior``, so a row the
  operator types in below the data — with an empty Scope cell — still
  counts towards the reported period, preserving the v0.3.117 guarantee.
* **Overhead rows keep their live formulas only where they can chain.**
  The selected window's Overhead amounts are SUMIFS against the Employee
  Register, which covers the reported months alone; the FY-prior block is
  written with plain values, exactly what its own sheet held. The offset
  row's ``=-SUM(...)`` span is computed per block, so it still backs out
  precisely its own heads.
* The Employee Register's one **bounded** row-range — the Office-Staff-
  Salary SUMIFS, bounded to dodge a circular reference — now starts past
  the FY-prior block via a new ``fy_offset``, so it still frames exactly
  the current window's salary rows.
* **"Provisions (FY)" stays.** A provisions sheet is a *balance
  outstanding* at the end of its window, not a register of rows; stacking
  two windows in one sheet would read as a total that was never owed.
* The year-on-year " (YTD)" / " (LY)" sets are untouched — they OVERLAP
  the reported period, so merging them would double-count.

Verified with a 71-check suite in three files. The decisive one generates
the SAME workbook twice from one database — once with this code, once
with the pre-merge code checked out in a git worktree — recalculates both
in real LibreOffice Calc, and compares every cell of all twelve reported
sheets (Cover, Dashboard, Budget vs Monthly Sales, Cost Centre P&L, both
Partner-Manager P&Ls, Entity P&L, Service MIS, Client Billing, Employee
Register, Client Register, Comparatives). Every figure is identical: the
merge changed the layout, not one number. Repeated for a two-month
selection and for an April selection whose prior window is the whole
previous financial year. Plus: the merged rows total per Scope exactly
what each old sheet held; a row appended in Excel with a blank Scope
counts towards the period while one hand-tagged "FY Prior" stays out; the
Register's bounded range provably starts past the FY block; and the app
still imports, builds every page, renders the HTML dashboard, and builds
from an empty database.

### v0.3.122 — Credit notes by hand; Client Billing totals the whole row

Two operator asks.

**1. Manual Entry can book a credit note.** The Voucher tab offered only
"Sales" and "Expense", and its amount box refuses negatives — so a credit
note (a sales return) could only get in via a Tally pull or an uploaded
register. The Type dropdown now has a third entry, **Credit Note (sales
return)**, and the form re-dresses itself for it: the amount reads
"Credit amount", a hint says the figure is entered positive and stored
negative, and the button becomes "＋ Add credit note".

* New ``manual_entry.VoucherType`` — ``(key, label, noun, kind, sign,
  vch_type)`` — is the vocabulary behind the dropdown, so the direction
  is a property of the TYPE, not something the form has to remember:
  ``add_voucher`` takes the type and applies ``sign * abs(amount)`` to
  both the amount and its tax. A 10,000 + 1,800 credit note stores
  ``net −10,000``, ``tax −1,800``, ``gross −11,800`` and one split of
  −10,000, exactly the shape ``parsers._vch_side_and_sign`` and
  ``tally_xml`` already give an IMPORTED credit note. Because the sign
  lives in the amount, every SUMIFS in the workbook nets it off with no
  special case, and the row needs no Review step.
* ``vouchers.vch_type`` is written as ``"Credit Note"`` (Tally's own
  wording) rather than ``"Manual"``, so hand-entered and pulled credit
  notes read alike in the Review export.
* ``kind`` stays ``sales`` — a return reduces revenue, it is not an
  expense — so a credit note shares the Jul-26 "(manual entry)" sales
  batch with the invoice it reverses. Auto-generated voucher numbers
  therefore had to get stricter: ``MAN-<timestamp>`` alone could collide
  now that a sale and a credit note booked in the same second share
  ``kind``, so a taken number gets a counter suffix and the importer's
  ``(entity, kind, vch_no)`` natural key stays unique.
* A Debit Note still needs no entry of its own: this firm books one as a
  supplementary sales invoice, which is "Sales" here.

**2. Client Billing's Grand Total sums every column that follows it.**
Column B covered only the selected period's months and treated the
prior-FY months as context. It now spans C through the last month
column, so it reads as what the client has been billed across the whole
sheet — and a client billed only in an earlier month, which used to show
a Grand Total of 0, now shows its actual figure and sorts by it. Still a
live ``=SUM(C5:F5)``, not a baked value, so an edited or appended
Revenue row flows through to the total. The row sort follows the same
span. (The HTML dashboard's Client Billing table shows only the selected
months, so its Grand Total already summed the columns beside it —
unchanged.)

Verified with a 123-check suite across five files: the service layer
(31), the generated workbook recalculated in real LibreOffice Calc (29),
the layout edge cases — a two-month selection, an April selection whose
prior window is the whole previous financial year at 13 month columns,
a row appended in Excel after generation, an empty database (21), an
offscreen UI smoke of the voucher form (32), and an app-wide regression
that imports every module, builds every page, and renders the workbook
and HTML dashboard (10). Grand Total equals the sum of its month cells
on every row and window; Client Billing's TOTAL ties to the whole
Revenue register (₹11,98,000); a hand-entered −40,000 credit note nets
Dorado Inc's July from 1,00,000 to 60,000 on the Revenue sheet, the
Client Billing cell, the Cost Centre P&L and the HTML dashboard alike;
and the recalculated workbook carries no Excel error values.

### v0.3.121 — "Compare with" is gone; every comparison is derived

Operator ask, in three parts: drop the comparison month-picker, give the
Partner-Manager P&L **one** column for the reported month and **one** for
the earlier months of the financial year, and turn the "(Cmp)" sheet into
a **year-on-year** view.

**1. The "Compare with" section is removed from the app.** The operator
picks the reporting month(s) and nothing else. Every comparison in the
workbook is now derived from that one choice, so there is no way to
produce a mismatched pair by accident. `report.build_windows()` derives
three spans, all computed with the same calc engine so every figure stays
a live `SUMIFS`:

| Window | For a Jun-26 MIS | Where it shows |
|---|---|---|
| **FY so far** — the FY months BEFORE the selection | Apr-26 to May-26 | one column per partner block on the Partner-Manager P&L; a column per month on Client Billing; a row per month on the Client Register |
| **Year to date** — April through the reported month | Apr-26 to Jun-26 | "Partner-Manager P&L (Cmp)", Comparatives |
| **Same period last year** | Apr-25 to Jun-25 | the same two sheets |

**2. Partner-Manager P&L — two columns, not many.** Each partner block
ends with `Jun-26 | Apr-26 to May-26`. v0.3.120 broke the earlier months
out one column per month; with eight partners that ran past a hundred
columns and was unreadable, so the cumulative column is back (the
v0.3.102 shape). A selection starting in April still shows the whole
previous FY there, as it has since v0.3.102.

**3. "Partner-Manager P&L (Cmp)" is now year-on-year.** Per partner:
`Apr-26 to Jun-26 | Apr-25 to Jun-25 | Δ`, on the full P&L line plan,
read from new `" (YTD)"` and `" (LY)"` data-sheet sets. Both windows have
their own sheets because the year to date CONTAINS the reported month —
merging them into the main registers would double-count. **Comparatives**
follows the same two windows, per cost centre, with both sides built by
the SAME formula so the columns are like for like; its per-partner profit
ties to the (Cmp) P&L's Net Profit exactly.

The year to date is a true year to date: it fills any gap a
non-contiguous selection leaves (Apr-26 + Jun-26 selected → the window is
Apr-26..Jun-26, May included), which is why it needs its own data rather
than being derived by adding two columns together.

**Provisions** go back to one snapshot per sheet — the balance
outstanding at the end of that window, named in the **As At** column
(v0.3.120) but no longer filtered on, so an appended row still counts.
They are a carried-forward stock, never a sum of months.

The **Cover** carries the three derived windows ("Previous months this
FY", "Year to date", "Same period last year") in place of the old
comparison row, and the Generate page's preview shows the totals for all
three before the operator exports.

Verified with a 301-check suite driving **real Excel** plus a 33-check
offscreen UI smoke. The seed now holds a full prior financial year, so
the year-on-year columns are checked against real figures rather than
zeros. Every window is proved equal to a fresh calc-engine run, line by
line, for each partner: a Jun-26 MIS reads PM 60,000 for the month and
1,40,000 for Apr–May; the (Cmp) sheet reads 2,00,000 against last year's
1,55,000 with a Δ of 45,000, and a 5,00,000 Sep-25 invoice inside last
year's FY but outside Apr–Jun provably stays out. Also verified:
Comparatives ties to the (Cmp) P&L; provisions read 1,00,000 outstanding
at end-May and 60,000 at end-June (never 1,60,000); an April MIS shows
Apr-26 vs Apr-25 alongside the whole previous FY; a non-contiguous
Apr+Jun selection still produces an Apr..Jun year to date; a row appended
to Revenue with a blank Scope counts in the reported month only and the
same row tagged `FY Prior` moves to the FY-so-far column; a row appended
to the (YTD) register reaches the year-on-year sheet and nothing else;
the whole workbook still ties out to the calc engine sheet by sheet; and
an empty database still builds. The UI smoke proves the "Compare with"
box, its list and its methods are all gone, that only the period and
location lists remain, and that the v0.3.119 selection rules still hold.

### v0.3.120 — Previous months, month by month — and the comparison selection decides which

Two operator asks about the columns beside the reported month, plus the
Client Register:

**1. The previous months are now one column EACH.** A Jul-26 MIS used to
show a single lumped "Apr-26 to Jun-26" cumulative column per partner
(v0.3.102). Every partner block on the **Partner-Manager P&L** now ends
with **Apr-26 | May-26 | Jun-26 | Apr-26 to Jun-26** — a column per month
of the financial year so far, then their total — and the "MIS Total"
block carries the same set. Each month column is a live partner-level
`SUMIFS` keyed on that month's Period label, so it shows exactly what
that month's own MIS would have shown; the %s recompute inside their own
column, so each is a true ratio of that month's figures. A window
spanning a single month gets no (duplicate) total column.

**2. Ticking comparison months produces ONLY those months.** Leave
"Compare with" empty and the previous-months columns are the financial
year to date, as above. Tick months there and exactly those months are
produced — no FY expansion, and the workbook carries no `" (FY)"` data
sheets at all; the columns read the `" (Cmp)"` sheets instead. One
`PriorWindow` object now carries the months, the data-sheet suffix and
the calc-engine data for whichever of the two cases applies, so the P&L,
Client Billing, the Budget data sheet, the Client Register and the HTML
dashboard all follow the same window. The Cover states it in two new
rows — **Previous months shown** and **Previous months from**
("financial year to date" / "selected comparison month(s)"). A month
ticked in BOTH lists is dropped from the window: it already has its own
reported column. The Generate page's comparison box now explains the
rule.

**3. The Client Register covers the previous months too.** A Jul-26 MIS
lists Apr-26, May-26 and Jun-26 above the reported month — in the
summary, the roster and the "Clients by cost centre" block — so the
year's client movement reads in one place. A new **Scope** column marks
each month "Previous" or "Reported"; it is a label, so every count stays
keyed on the Period alone. "New" still means first-billed-ever across all
history, which is why a client billed back in Mar-26 does NOT read as new
in Apr-26. The HTML dashboard's Client Register section shows the same
months.

**Provisions are a stock, not a flow.** They carry forward, so they can
never be summed across months. Each window's Provisions sheet now holds
**one snapshot per month**, stamped in a new **As At** column (H), built
by `calc.provisions_as_at`; a month column reads its own snapshot, and a
window total shows the LAST month's balance rather than a sum. The main
Provisions sheet is unchanged — one snapshot, no As At criterion, so an
appended row still counts.

**The v0.3.118 Scope contract is untouched.** The month columns carry the
Period criterion ON TOP of the Scope one: a row typed in below the
generated data with a blank Scope counts towards the selected period,
exactly as before, and tagging it `FY Prior` books it to its month's
column and the window total. Without that, one appended row would have
counted in both windows at once.

Verified with a 343-check suite driving **real Excel** (openpyxl only
writes formula strings; what matters is what Excel computes), plus a
19-check offscreen UI smoke. The central check is an equivalence proof:
every previous-month column, for every P&L line and every partner, is
compared against a fresh calc-engine run for that single month — Apr-26
reads 1,00,000 / May-26 40,000 / Jun-26 60,000 for PM against a Jul-26
reported 50,000, and the window total 2,00,000. Also verified: the
reported month's figures are byte-identical with an FY window, a
comparison window or none at all; the window total never leaks into the
partner Total or the MIS Total; provisions read 1,00,000 / 1,00,000 /
60,000 across Apr/May/Jun with a window total of 60,000 (not 2,60,000)
and an MIS window total of 85,000; a ticked May-26 comparison produces a
May-26 column and no Apr/Jun columns, with no `(FY)` sheets and no
`Scope = "FY Prior"` rows anywhere; an Apr-26 MIS lays out all twelve
months of the previous FY and picks up its lone Mar-26 sale; a
non-contiguous Apr+Jun selection still bakes the uncovered May budget
value while Apr stays live; the degenerate "compare July with July" case
produces no previous columns but keeps the comparison sheets; a blank
Scope row appended in Excel lands in the reported month only and the same
row tagged `FY Prior` lands in May and the window total; the whole
workbook still ties out to the calc engine sheet by sheet (Cost Centre
P&L, Entity P&L, Service MIS, Employee Register's overhead cascade,
Dashboard KPIs, Cover totals); and an empty database still builds.

### v0.3.119 — Generate MIS no longer silently selects the whole financial year

Operator report: "when a comparison MIS is generated, with selected
months, the output comes for the whole period of that FY."

Root cause, in the Generate page's month list. `_reload_periods` ticked
each month with `p in checked or not checked` — so whenever NOTHING was
ticked it re-ticked **everything**. `showEvent` calls that method on
every visit to the page, which meant:

* the very first visit pre-ticked **every month on record**, not one; and
* clearing the list and navigating away and back silently restored the
  full selection.

An operator who opened the page, ticked a comparison month and pressed
Generate therefore got an FY-wide MIS instead of the month they meant —
the reported symptom exactly. Nothing in the workbook code was wrong;
the wrong `periods` were handed to it.

* **The latest month is pre-ticked once**, on the first show — the firm
  reports monthly, so that is the overwhelmingly common run.
* **After that the selection is preserved exactly, including an empty
  one.** Nothing may ever widen it on its own: a freshly imported month
  now arrives **unticked**, so an import cannot quietly pull extra months
  into the next report either.
* **Both group-box titles show the live selection** — "Reporting
  period(s) — Jun-26", "Compare with — May-26", "…— none selected", and
  a compact "N months" for long non-contiguous lists. The complaint was
  about generating an FY-wide MIS *without realising it*, so what is
  ticked has to be readable without scrolling the list.

Verified with a new 22-check UI suite driving the real page: the first
show ticks exactly the latest month (and provably NOT the whole FY); an
explicit two-month selection survives repeated re-shows; a CLEARED list
stays cleared across a re-show (the bug — this check fails against
v0.3.118); ticking a comparison month leaves the reporting months
untouched and both survive a re-show; a newly imported July arrives
unticked; "Select all" still works and an explicit full-FY selection
survives; and end to end, the default run's `MISOptions` carries one
period, whose Cover reads "Jul-26" and whose Revenue "Current" rows
cover only that month. Re-ran the v0.3.118 suites unchanged (93 + 20
checks, real Excel, against a v0.3.117 worktree as the pre-merge
baseline) plus a main-window smoke that navigates in and out of Generate
MIS three times and confirms the selection holds.

**No code change for the other half of the report** ("Client Billing's
current-month figures are not formula-derived"): those cells became live
`SUMIFS` over the Revenue sheet in **v0.3.117**, and still are. A
workbook showing baked values there was generated by **v0.3.116 or
earlier** — the operator's installed copy needs to be on v0.3.117+.

### v0.3.118 — Revenue and Expenses are one sheet each (the "(FY)" editions merged in)

Operator ask: merge "Revenue" with "Revenue (FY)", and "Expenses" with
"Expenses (FY)". Those pairs held the same kind of transaction for two
different month windows — the SELECTED MIS period, and the financial-year
months before it that feed the Partner-Manager P&L's cumulative column
(v0.3.102). Reading a client's or a partner's year meant hopping between
two sheets. Now there is **one Revenue register and one Expenses
register**, each covering the whole FY-to-date.

* **A new `Scope` column** — `Revenue` col **K**, `Expenses` col **M** —
  says which window a row belongs to: `Current` (the selected period) or
  `FY Prior`. Rows are written chronologically: the FY-prior months
  first, then the selected period's. Every pre-existing column keeps its
  letter (Revenue A–J, Expenses A–L), so nothing that referenced them
  moved.
* **Aggregates carry a Scope criterion.** The Cost Centre P&L, the
  Partner-Manager P&L's leaf/subtotal columns, Entity P&L and Service MIS
  report the selected period, so their SUMIFS gained
  `Scope <> "FY Prior"`; the PM P&L's FY-cumulative column gained
  `Scope = "FY Prior"`. The current-window test is the **negation**
  deliberately: a row the operator types in below the generated data has
  an empty Scope cell, and Excel's `<>` criteria match empty cells — so
  an appended row still counts towards the selected period, keeping the
  v0.3.117 "everything I added counts" guarantee. Typing `FY Prior` in
  the Scope cell is the way to book an added row to the earlier window
  instead.
* **Period-keyed formulas got SIMPLER, not more complex.** Client
  Billing's month columns and the `Budget Sales (Monthly)` data sheet used
  to pick their source sheet per month (`Revenue` vs `Revenue (FY)`);
  they now read the one sheet and key on the Period label alone. That is
  safe because the two windows never share a month —
  `_fy_prior_periods` returns months strictly before the earliest
  selected one — and it means an appended row with a blank Scope still
  reaches them. The Employee Register's office-indirect pool was already
  period-keyed and is untouched.
* **" (Cmp)" stays a separate sheet.** The comparison period is
  operator-chosen and may OVERLAP the FY-prior window (a June MIS
  compared against May, with May also in the cumulative window), so
  merging it would double-count. `Salary`, `Reimbursements` and
  `Provisions` keep their `(FY)` editions — only the two sheets the
  operator asked about were merged.

Verified with a new 93-check suite plus a 20-check edge-case suite, both
driving **real Excel** (openpyxl only writes formula strings; the whole
point of this workbook is what Excel computes). The central check is an
equivalence proof: the same database is rendered by the pre-merge code
and the new code, both recalculated by Excel, and **every summary sheet
compared cell for cell** — Cover, Dashboard, Budget vs Monthly Sales,
Budget Sales (Monthly), Cost Centre P&L, Partner-Manager P&L, Entity
P&L, Service MIS, Client Billing, Employee Register, Client Register,
and on a comparative run also Comparatives and Partner-Manager P&L
(Cmp). Every figure is identical; the only difference anywhere in the
workbook is the PM P&L footnote, which now names the Scope rows instead
of the old sheets. Also verified: the merged sheets carry every row from
both former sheets, byte-identical in the data columns and in
chronological order; the two windows never share a month label; PM's
June revenue reads 50,000 and not 190,000 (it has 140,000 in the FY
window — the figure a missing Scope criterion would produce); a row
typed onto Revenue with an EMPTY Scope flows into the CC P&L, the PM
P&L current total, Client Billing, the Budget month cell and the
open-ended subtotal, while staying out of the FY column; the same row
tagged `FY Prior` does the reverse; an appended Expenses row behaves the
same; a comparison against May (inside the FY window) keeps the (Cmp)
column at May's 60,000 rather than double-counting; an April-start MIS
(whose FY window is the whole empty previous FY) evaluates to 0
cumulative with the current figures intact; a non-contiguous Apr+Jun
selection still bakes the uncovered May value; and an empty database
still builds. The UI smoke across all eight pages stays green.

### v0.3.117 — Manual rows added in Excel post-generation count everywhere

Operator report: the Revenue sheet's filtered-subtotal row didn't pick
up rows typed in below the generated data. Fixed, plus a full audit of
every place a manually-added row could be missed:

* **Data-sheet subtotals are open-ended.** Every data sheet's top
  ``=SUBTOTAL(109,…)`` row (Revenue / Expenses / Salary /
  Reimbursements / Provisions / Budget Sales (Monthly), plus the (Cmp)
  and (FY) editions) now runs to the sheet bottom (row 1,048,576)
  instead of stopping at the last generated row — a row typed below
  the data counts. Appended rows sit past the AutoFilter range so the
  filter can never hide them: they are ALWAYS included, coherent with
  "everything I added counts".
* **Client Billing's current-month cells were the last baked values**
  on that sheet — a manual Revenue row never reached them. They are
  now live SUMIFS over the "Revenue" sheet by Client + Period label
  (exactly like the prior-FY columns over "Revenue (FY)" since
  v0.3.109), so additions/edits flow into the month cell, the Grand
  Total and the TOTAL row.
* **Audit of every other figure**: the CC P&L, PM P&L (+ (FY)/(Cmp)),
  Entity, Service, Budget (v0.3.116 chain), Employee Register and
  Comparatives all read FULL-COLUMN SUMIFS over the data sheets — they
  already captured appended rows. Three bounded ranges remain, each
  deliberately: summary-sheet filtered subtotals (extending them would
  double-count their own TOTAL rows), the Salary sheet's overhead
  offset (must back out exactly its heads block, v0.3.106), and the
  Employee Register's office-staff-salary window (a full column would
  be an Excel circular reference through the Overhead rows — the one
  documented spot a manually appended Pool-Source salary row can't
  reach).

Verified (suite now 36 checks): the three populated data sheets carry
open-ended subtotal ranges; after typing two rows onto the generated
Revenue sheet the subtotal evaluates 45,000 → 55,333; Client Billing's
month cells are SUMIFS and its "(unmapped)" June cell + Grand Total
follow to 55,333; the whole v0.3.116 budget chain keeps working; and
the April-only edge stays correct. All eight prior suites (updated
v109 expectation: the June cell is now evaluated, same figure) and the
UI smoke stay green.

### v0.3.116 — Budget Sales (Monthly) is formula-driven down to the transactions

Follow-up on v0.3.115: the month columns read the new "Budget Sales
(Monthly)" data sheet, but THAT sheet held baked values — so a sales
row the operator adds or edits in Excel post-generation never reached
it. The data sheet's Sales cells are now **themselves live SUMIFS over
the transaction-level Revenue sheets**, completing the chain:

* A month in the SELECTED period reads the **"Revenue"** sheet; an
  earlier FY month reads **"Revenue (FY)"** (the same window v0.3.102
  writes for the PM P&L cumulative column) — together the two sheets
  cover the whole FY-to-date. Criteria: partner code (col D) +
  Category ``"Income"`` (col I — reimbursement/OPE recoveries stay
  excluded) + Period label (col J, added in v0.3.109).
* **Zero months get a row too** (previously omitted): a sale ADDED on
  a Revenue sheet for a month that had nothing still flows through.
* A month covered by neither sheet — only possible with a
  non-contiguous period selection — keeps a baked value.

So: edit/add a row on Revenue or Revenue (FY) → the data sheet cell
recomputes → the month cell on Budget vs Monthly Sales → its YTD,
Variance vs Budget, Average and the TOTAL row, all live.

Verified with the suite grown to 29 checks: every data-sheet cell is a
SUMIFS with the right source (selected→Revenue, prior→Revenue (FY),
never the prev-FY sheet on an April-only run), zero-month rows exist,
all v0.3.115 figures evaluate identically through the extra formula
hop — and the end-to-end ask itself: a June sale typed onto the Revenue
sheet post-generation lifts PM's Jun cell 50,000→57,000 (an added OPE
row is correctly ignored), an edited Revenue (FY) row lifts KS's May
20,000→25,000, and YTD / Variance / TOTAL all follow. All eight prior
suites and the UI smoke stay green.

### v0.3.115 — Budget vs Monthly Sales: month columns are now formula-driven

Operator ask: the per-month columns on the "Budget vs Monthly Sales"
sheet were baked values — make them formula-driven like the rest of the
workbook. They were the last hard-coded cells on the sheet (YTD /
Variance / Average were already formulas). The reason they were baked:
the Revenue data sheet only holds the SELECTED MIS periods, but this
sheet always shows the full **FY-to-date**, so a SUMIFS over Revenue
would miss any FY month that wasn't selected (e.g. a June-only run
still shows Apr + May columns).

Fix: a companion data sheet **"Budget Sales (Monthly)"** is written with
one row per (partner, FY-to-date month, sales) — pulled from the SAME
``monthly`` dict the values used to come from, so the figures are
identical, only now formula-backed. Each month cell is a live
``=SUMIFS`` keyed on the partner **code** (column A of its row) and the
month **label** (the column's header cell). Editing a sales figure on
the data sheet now recomputes that month cell, its YTD, Variance and
Average — the whole row stays live. Sales-only (Income) filtering,
credit-note negatives and the FY-to-date span are unchanged; the HTML
dashboard reads the same ``monthly`` dict so the two still agree by
construction.

Verified with a 19-check suite generating a **June-only** MIS (so the
Apr/May columns are provably NOT in the Revenue sheet): every month
cell is a SUMIFS over the companion sheet; the data sheet holds exactly
the non-zero Income rows (OPE/reimbursement excluded, zero months
omitted); formula evaluation gives Apr 100,000 / May 0 / Jun 50,000 for
PM and 30,000 / 20,000 / −5,000 for KS, with YTD 150,000 / 45,000, the
Variance and the TOTAL row all tying; and ``budget_monthly_data`` (the
dashboard's source) is unchanged. All eight prior suites (14+14+21+30+
34+48+70+28 checks) and the UI smoke stay green.

### v0.3.114 — Records ▸ Salary: Edit / Delete; Source column on every tab

Two operator asks:

**1. Salary rows get the same Edit / Delete actions as Reimbursements
(v0.3.108).** New ``EditSalaryDialog``: Month/Year (salary is on the
calendar month per the decisions log), Employee, Cost centre + Entity
master dropdowns, Category, Salary paid and Reimbursement. The cost
centre picked here is the source of truth the MIS reads; the raw
sheet text (``raw_cost_centre`` / ``raw_entity``) stays stored
untouched for reference. Delete confirms with the row's figures and
removes exactly that entry. New ``records.update_salary`` /
``delete_salary`` services; the listing now carries the row id and
the resolved FK ids for prefill.

**2. A Source column on every Records line-item tab** (Salary,
Timesheet, Reimbursements) so the operator can tell where each entry
came from: **"Manual entry"** for rows added on the Manual Entry page,
otherwise the uploaded / pulled **file's name** (one shared
``_source_label``; the Reimbursements tab's existing column now uses
the same label). Plain read from the row's import batch — no schema
change, no data touched.

Verified with a 14-check suite: Source values on all three tabs
(file name vs Manual entry), Edit/Delete buttons per salary row, the
dialog's full prefill, an edit persisting period/CC/amounts while
leaving the raw sheet text and row count untouched, calc picking up
the edited figure, and delete removing exactly one row. All seven
prior suites (245 checks) and the UI smoke stay green.

### v0.3.113 — Expenses sheet: Invoice No now comes through the Tally pull

Operator report: the generated MIS's Expenses sheet had a blank
"Invoice No" column. Root cause: only the **Excel** voucher-dump parser
read the register's "New Ref" / "Agst Ref" bill references — the
**direct Tally HTTP pull** (the operator's normal flow since the Tally
Pull page shipped) never extracted them from the XML, so every pulled
voucher stored ``invoice_no = NULL`` and the sheet's column C (which
was wired correctly all along, calc → fact → sheet) had nothing to
show.

* **``tally_xml._bill_refs``** — reads ``BILLALLOCATIONS.LIST`` under
  the party ledger entry of each voucher: ``NAME`` is the reference,
  ``BILLTYPE`` says New Ref (fresh invoice) vs Agst Ref (settling an
  old one). Same rule as the Excel parser: New Refs preferred, Agst
  Refs the fallback, several references joined with ", ".
* **Re-pull backfills history.** Vouchers pulled before this fix hold
  no invoice number, and a re-pull skips them as identical duplicates —
  the dedup skip now **fills in an EMPTY invoice_no as it passes**
  (never overwrites an existing one; amounts and every other field
  untouched). So the operator just re-pulls the old periods once and
  the numbers appear, with zero duplicate risk.
* The Revenue sheet's "Invoice No" column intentionally keeps showing
  the sales voucher number — for the firm's own invoices that IS the
  invoice number.

Verified with a 14-check suite: extraction across every shape (New
Ref, Agst-only, multiple refs joined without mixing in Agst, no
bill allocations, amounts unaffected), commit persisting the numbers,
the re-pull inserting nothing while backfilling exactly the blank
rows and preserving non-blank ones, and the generated workbook's
Expenses sheet carrying the reference on the voucher's row. All six
prior suites (21+28+30+34+48+70 checks) and the UI smoke stay green.

### v0.3.112 — Review & Map no longer hangs; CC-strings tab crash fixed

Operator report: the app still lagged when navigating to Review & Map ▸
Vouchers after v0.3.111. Profiled on a realistic 2-year dataset (24k
vouchers, 100k timesheet rows, 1.5k clients, 2k permanently-unmapped
vendors): opening Review & Map took ~2.9s and every keystroke in the
Clients search ~1.6s. After this release the page opens in ~0.36s and
keystrokes are instant — and a long-standing crash was found and fixed.

* **Bug fix: the Cost Centres tab has been silently broken.**
  ``CcStringTab.reload`` used ``transaction()`` without importing it —
  a ``NameError`` on every reload since at least v0.3.94 (PySide6
  prints the traceback and carries on, so the tab just showed stale /
  empty data, and under the old eager refresh the exception also
  aborted the voucher-tab reload behind it). Import added; the tab
  works again.
* **The fuzzy client-name pass ran twice per navigation** — once at
  page level and AGAIN inside ``ClientTab.reload`` (1.1s each at this
  scale, re-scoring every unmapped vendor against the whole client
  master), plus on every search keystroke. Navigation now runs the
  exact-match pass only (0.06s — it finds everything a master edit can
  make matchable); the FULL fuzzy pass still runs where it can find
  new links: after every import / manual-entry save, and via the
  Clients tab's ⚡ Auto-resolve button.
* **Search keystrokes refilter in memory.** The three queue tabs
  (Clients / Employees / Cost Centres) cached nothing — each keypress
  re-ran resolution + re-queried + re-rendered. They now fetch once on
  activation and refilter the cached queue per keystroke.
* **Render caps everywhere widgets grow with data.** Queue tabs and
  the voucher tab render the first 400 rows (v0.3.111's 1,000 was
  still sluggish on modest hardware) with a "Show all N rows" button;
  counts, totals, info labels, badges, search and the bulk actions
  ("Create all as new", Confirm suggested) always cover the FULL
  queue. Records ▸ Reimbursements (Edit/Delete widgets per row) pages
  at 500 with the existing Load-all.

Measured after: Review page open 2.88s → 0.36s, Clients reload 1.64s →
0.16s, CC tab crash → 0.015s, voucher tab activation 0.65s → 0.53s
(query-bound), Records Reimbursements 0.06s. Verified with a new
21-check suite (spy asserts nav runs skip_fuzzy while the import hook
runs full fuzzy; CC tab loads 600 strings with suggestions; caps +
Show-all on every tab; keystroke refilter provably does NOT hit the DB;
search reaches rows beyond the render window; row counts across all
tables byte-identical after the whole UI drive) — plus all five prior
suites (28+70+48+34+30 checks) and the UI smoke, all green.

### v0.3.111 — Performance at scale: indexes, lazy navigation, capped rendering

Operator ask: the data will grow over time — make sure the app never
hangs or slows down, especially navigation, without touching any data.
A full audit found three compounding costs; all fixes are read-path
only (indexes + UI laziness), so every stored row is untouched
(verified: row counts and amounts identical through the migration).

**1. Migration 21 — eleven indexes on the hot queries** (pure DDL):
* ``batch_id`` on vouchers / timesheet / salary / reimbursements — the
  Records ▸ Import batches tab runs one correlated COUNT per batch × 4
  tables; each was a full table scan.
* **Partial indexes** on the unresolved rows (``WHERE client_id IS
  NULL`` on vouchers/timesheet/reimbursements; ``WHERE cost_centre_id
  IS NULL`` on voucher_splits) — the Review queues, tab badges and
  Dashboard review tiles scan only still-unresolved rows, so these
  stay tiny however large the resolved history grows.
* **Expression indexes** on ``lower(trim(emp_name))`` (timesheet) and
  ``lower(trim(employee_name))`` (salary) — the unknown-employee queue
  grouped the entire timesheet (the largest table) on every refresh.
* ``vouchers(client_id)`` — Client Register first-billing GROUP BY.
Verified with EXPLAIN QUERY PLAN that each hot query actually uses its
index. (WAL / synchronous=NORMAL / 64MB cache were already in place.)

**2. Review & Map navigates lazily.** Showing the page used to run the
three auto-mapping passes AND rebuild all four tabs — including the
voucher tab's widget-heavy table over every voucher ever imported.
Now only the CURRENT tab loads; every tab reloads fresh from the DB
the moment it's activated, so nothing shown is ever stale. The tab
badges come from the (now-indexed) unresolved-count queries instead of
each tab's loaded rows — correct even for never-visited tabs. The
import/manual-entry ``refresh()`` hook keeps the auto-mapping passes
but no longer builds hidden tables. The voucher tab also no longer
loads in its constructor.

**3. Vouchers tab render cap.** Each table row carries five widgets
(status pill, two buttons, …) — thousands of rows froze the tab. The
DB fetch and Python-side filtering still cover EVERYTHING (the totals
bar, the "n of m" summary and the unassigned badge are exact over the
full filtered set, and search reaches every row), but only the first
1,000 rows get widgets, with a "Show all N rows" button (summary notes
the truncation). Edit/Delete index mapping stays safe because the
rendered set is a strict prefix of the filtered rows.

Verified with a 28-check suite on a 2,500-voucher / 3,000-timesheet-row
database: migration integrity (every table's row count and the voucher
sum unchanged, idempotent re-run, all 11 indexes present), six query
plans, the capped-render behaviours, lazy navigation (voucher tab not
loaded on page show OR hidden refresh; badges right without loading;
activation loads fresh), and a calc + workbook smoke. All four prior
suites (70 + 48 + 34 + 30 checks) and the UI smoke stay green.

### v0.3.110 — Review & Map ▸ Vouchers: search by amount

Operator ask: find a voucher by its amount. The Vouchers tab gains an
**Amount** filter box beside the text search (they combine):

* ``50000`` / ``₹ 50,000`` / ``=50000`` — exact amount, ±0.50 paise
  tolerance, sign-insensitive (a −11,800 credit note matches
  ``11800``)
* ``>10000`` ``>=10000`` ``<5000`` ``<=5000`` — comparisons on the
  magnitude
* ``10000-20000`` — inclusive range (order-insensitive)

A voucher matches when its **net or gross** amount satisfies the query,
so the operator can type either the P&L figure or Tally's tax-inclusive
total; a zero/unset component is ignored so it can't trivially satisfy
a ``<`` query. Blank or still-being-typed text leaves the filter
inactive. Debounced like the text search; the live totals bar and the
"n of m" summary follow the narrowed set (parser:
``review_page._amount_query_predicate``).

Verified with a 30-check suite: 16 parser cases (blank/partial input
inactive, comma/₹ stripping, gross matching, boundaries on every
operator, range order, leading-minus vs range) and a headless
VoucherTab drive over planted vouchers — exact by net, exact by gross,
credit-note magnitude match, lakh-formatted input, comparisons, range,
AND-combination with the text search, filter clearing, and the
summary/totals bar following. UI smoke + full compile green.

### v0.3.109 — Reimbursements follow the employee; month-wise billing history; reimbursements in the overhead pool

Three operator asks in one release:

**1. Reimbursement outlays book to the EMPLOYEE's cost centre.** The
Cost Centre P&L / Partner-Manager P&L reimbursement SUMIFS now key on
the Reimbursements sheet's **Employee CC column (E)** instead of the
client's partner (C) — the cost follows the team member who spent the
money. Changed at the SOURCE so everything stays tied: calc's
reimbursement facts book ``employee CC → client's CC → Office``
(employee first; the old chain was client-first), and the sheet's
column E now shows that booked CC while column C (renamed **Client
CC**) keeps the client's partner for reference. Repointed everywhere
the formula appears: the CC P&L, the PM P&L partner columns, and —
via the shared ``_pm_leaf_formula`` — the **(FY)** cumulative and
**(Cmp)** comparison editions, whose sheets share the same writer so
their column layout moves in lockstep. Dashboard and Comparatives read
the calc lines, so they follow automatically.

**2. Client Billing: month-wise FY history, not a cumulative.** The
single "Cum Apr-26 to May-26" column becomes **one column per FY month
before the selected period** — a June MIS shows Apr-26 and May-26
columns, each a live SUMIFS over the "Revenue (FY)" data sheet by
Client + its new **Period column (J)**. Grand Total still sums ONLY
the selected period's columns; clients billed only in the earlier
months still get a row; freeze pane holds Client + Grand Total.

**3. Office staff reimbursements join the overhead pool.** The
Employee Register summary gains **"Office Staff Reimbursement (₹)"**
(column H): the reimbursement-sheet outlays of employees whose home
cost centre is Office, which now feed the overhead pool exactly like
office-home salaries — Pool = Office Indirect + Office Staff Salary +
Office Staff Reimbursement, spread over the recipients. Formula-driven
via a new **Pool Source column (J)** on the Reimbursements sheet
("Yes" on office-home rows within the selected locations — the same
strict rule as the Salary sheet's Pool Source; a location-excluded
office employee's outlay stays on Office). Since those rows also book
to Office under ask 1, the pool's offset backs them out — the firm
total is invariant, verified with and without a location filter.
Summary columns shift right (Recipients I, Pool J, Per-head K; the
Salary sheet's overhead rows repointed; headcount block moves to M).

Verified with a new 34-check suite (plus the updated 70-check ER/
Records suite, the 48-check cycle suite and a UI smoke, all green):
a KS employee's outlay for PM's client lands on KS with PM kept as
Client CC; an unknown employee falls back to the client's CC; CC P&L
rows formula-evaluate to 500/200/700 per the new booking; every
reimbursement SUMIFS across the main, (FY) and (Cmp) sheets keys on
$E:$E; the ER pool cascade evaluates 12,000+5,000+700 → 17,700 ÷ 10
heads = 1,770 per head with the Salary sheet's overhead netting to
zero; a Mumbai-only run feeds only the Mumbai office employee's 300
into the pool with the firm net identical; Client Billing shows
Apr/May/Jun columns with ClientP 100,000/50,000/25,000, a zero-current
ClientQ row, no Cum column, and Grand Total = current only; the
comparative workbook builds with matching (Cmp) columns.

### v0.3.108 — Records ▸ Reimbursements: per-row Edit / Delete actions

Follow-up to the v0.3.107 tab: each reimbursement row now carries
**Edit** and **Delete** buttons (matching the Review & Map tabs' inline
actions), so a single wrong entry can be fixed or removed without
deleting the whole import batch.

* **Edit dialog** (``EditReimbursementDialog``) — Date (with a "has a
  transaction date" toggle), Month/Year, Employee, Client, Amount and
  the client-reimbursable flag. The period follows the system's own
  rules: while a date is set the Month/Year dropdowns are disabled and
  a live note shows the MIS month the 21st→20th cycle derives from that
  date (edit the date, the note re-derives); untick the date to pick
  the month by hand (pivot/manual rows). **Retyping the client**
  clears the stored link and re-matches the new text against the client
  master / aliases immediately — a recognised name shows its canonical
  form straight away, an unknown one surfaces in Review & Map. Leaving
  the client text untouched preserves the existing link exactly.
* **Delete** — confirm dialog quoting the row (period · employee ·
  client · amount), then removes just that row.
* New ``records.update_reimbursement`` / ``delete_reimbursement``
  services; the listing query now carries the row id and client id.

Verified (suite now 69 checks, all green, plus the v0.3.105 cycle suite
and a UI smoke): every row renders Edit + Delete buttons; the dialog
prefills a dated row correctly and disables Month/Year while dated;
moving the date from 25 Apr to 25 May re-buckets the row to the June
MIS on save; amount/flag edits persist; an untouched client keeps its
raw text and link; a retyped client auto-relinks to the master and the
tab immediately shows the canonical name; a dateless manual row edits
via Month/Year with no date stored; delete removes exactly the one row.

### v0.3.107 — Consider gates only the overhead; Records gains a Reimbursements tab

Two operator refinements on v0.3.106:

**1. "Don't consider" is only about the overhead per-employee cost.**
The Employee Register's headcounts are a whole-firm status overview:
the summary's Active / New Joiners / Exits columns and the
**headcount-by-cost-centre block now count EVERYONE**, whatever
locations were selected — a Bangalore employee in a Mumbai-only MIS
still shows under her cost centre as Active. Only the
office-overhead computation reads the Consider flag: Overhead
Recipients (and therefore pool ÷ heads) counts "Consider" rows alone,
in calc, in the sheet's COUNTIFS, and in the overhead labour facts.
Flipping a dropdown still live-recomputes the recipients and per-head
figures — but no longer changes the headcounts. The dashboard's
headcount charts follow the same whole-firm rule, staying tied to the
workbook.

**2. Records ▸ Reimbursements tab.** Until now there was NO way to see
stored reimbursement rows in the app before generating the MIS. The
Records page gains a **Reimbursements** tab mirroring Salary /
Timesheet: period dropdown (defaults to the latest; "(all periods)"
available), debounced employee + client filters, paged loading with
"Load all", and a totals line (rows · employees · amount · the
client-reimbursable slice). Columns: Period, Date, Employee, Client
(canonical master name once resolved, else the raw upload text),
Amount, Client reimbursable, and **Source** — the uploaded file's name,
or "(manual entry)" — so Excel-imported and manually-added rows are
both visible and distinguishable. New read-only queries
``records.list_reimbursements`` / ``reimbursement_totals`` /
``list_reimbursement_periods``; the tab hint spells out the 21st→20th
cycle bucketing.

Verified with the expanded 54-check suite (plus the v0.3.105 48-check
suite and a UI smoke, all green): headcounts count Don't-consider rows
(calc, formula-evaluated summary cells, the by-CC block showing the
excluded employees under their CCs, dashboard series) while recipients/
pool/per-head stay strict and the firm net stays invariant across
location selections; a what-if flip still recomputes Recipients 7→8 and
per-head with overhead netting to zero, and now leaves the Active count
untouched; the Reimbursements tab lists an imported row and a manual
entry side by side with correct date/client/amount/source, totals line,
default period, and working employee/client filters.

### v0.3.106 — Employee Register shows everyone, with a Consider dropdown

Operator ask: the Employee Register should show **all** employees even
when the MIS is generated for specific locations, with an extra column —
a two-value dropdown, **"Consider" / "Don't consider"** — that tells
both the reader and the sheet's own formulas which rows enter the
computation. "Consider" = the employees (and partners) of the locations
selected before generating; everyone else reads "Don't consider".

* **calc** — every timesheet-active employee, every exit and every
  active partner now enters the register roster regardless of the
  location selection; each member carries a ``considered`` flag (the
  strict v0.3.101/104 location filter decides the flag, not the
  presence). All headline figures — Active / New Joiners / Exits /
  Overhead Recipients / pool / per-head — and the overhead labour facts
  count ONLY considered members, so the system output is unchanged; the
  firm net stays identical across any location selection (verified).
  The untagged-employee/partner warnings now say the rows are marked
  "Don't consider" rather than left out.
* **Employee Register sheet** — the roster gains a **Consider** column
  (G) with an in-cell dropdown (Excel data validation, exactly the two
  values). Every COUNTIFS on the sheet — summary Active/New/Exits, the
  Overhead Recipients cell, and the headcount-by-cost-centre block —
  carries the ``"Consider"`` criterion, so the counts, the pool ÷ heads
  per-employee figure, and the Salary sheet's Overhead rows that chain
  to it all **recompute live when the operator flips a dropdown**.
* **Overhead offset re-anchored.** The Salary sheet's negative Office
  offset was ``−(per-head × recipients)``; with flippable recipients
  that could drift from the head rows actually written at generation.
  It is now ``=−SUM(<its own heads block>)`` — it always backs out
  exactly what the written head rows charge, so the firm total stays
  balanced through any what-if flip (values identical at generation).
* **Dashboard** — the headcount-by-cost-centre chart counts considered
  members only, staying tied to the workbook's figures.

Verified with a 44-check suite (plus the v0.3.105 48-check suite and a
UI smoke, all green): flags for every case (right location, wrong
location, untagged employee, unresolved name, office-home staff,
untagged partner), counts/pool/per-head unchanged vs the strict filter,
firm-net invariance across none/one/other/both location selections, the
generated workbook formula-evaluates to the strict figures (via a mini
Excel evaluator), the roster shows every employee/partner with the right
flag and the dropdown validation on exactly the Consider range, a
what-if flip of a "Don't consider" employee live-recomputes Active,
Recipients and per-head while the overhead still nets to zero, and a
no-filter run shows everyone as "Consider" with unchanged figures.

### v0.3.105 — Reimbursements follow the 21st→20th cycle, like the timesheet

Operator ask: reimbursements should be considered from the **21st of the
previous month to the 20th of the current month**, exactly like the
timesheet — a reimbursement dated 25 Apr belongs to the **May MIS**
(May's window is 21 Apr → 20 May).

* **Parser** — the transaction date drives the bucket
  (``valueutils.mis_period_for_timesheet_date`` generalised to
  ``mis_period_for_cycle_date``, shared by both parsers). The date comes
  from the mapped ``date`` column or from a **date-typed** Period cell —
  the firm's export carries a "Transaction Date" column that operators
  map as the period, and those cells are real datetimes. A text month
  label ("May-26") has no trustworthy day (it text-parses as 26 May), so
  it keeps plain calendar semantics as the fallback for dateless rows —
  new ``valueutils.typed_date`` makes that distinction.
* **Migration 20** — existing reimbursement rows that carry a
  transaction date are re-bucketed in place (day ≤ 20 → that month,
  day ≥ 21 → next month). Dateless rows (pivot imports, manual entries)
  keep their stored period — there's no day to re-bucket by, and a
  manual period is the operator's explicit choice.
* **Dedup reworked — and a silent money-loss bug fixed.** The cycle
  merges rows from two upload files into one MIS month (April file rows
  dated ≥ 21 Apr + May file rows dated ≤ 20 May), so the transaction
  date joins the duplicate key. Testing against the real April export
  surfaced that the v0.3.90 set-dedup was silently dropping **32
  genuine rows** — same employee/client/amount/date but distinct
  expenses (two ₹20 metro rides the same day; "MGT 7A fees" vs "AOC4
  FEES") that the file's own pivot total counts. Dated rows now dedup
  as a **multiset**: a file's N identical rows all import, a re-import
  still inserts 0, and a corrected file with one more occurrence
  inserts exactly the extra one. Dateless pivot rows keep the strict
  v0.3.90 behaviour. **Re-importing past reimbursement files therefore
  restores the previously-dropped rows.**
* The batch's period label now also counts reimbursement rows
  (``_dominant_period``), so a reimbursement-only upload shows its
  period on the Records page.

Verified with a 48-check suite: cycle arithmetic (month/Dec→Jan
rollovers, 20th/21st boundary), typed-vs-text period cells, parser
precedence (date beats label; dateless rows fall back to the label),
timesheet parser regression, all dedup shapes (cross-file merge,
in-file genuine repeats, pivot files, re-import idempotence), the
migration on a v19 database (dated rows re-bucket, NULL/garbage dates
untouched, idempotent re-run) — and end-to-end on the REAL April + May
exports: all 1,198 rows import (0 lost), every bucket ties to an
independent recomputation from the raw files, a 25-Mar row in the April
file lands in April MIS, ``calc.compute`` for May equals the 21 Apr →
20 May outlays to the paisa, and the generated workbook's
Reimbursements sheet carries the right period labels.

### v0.3.104 — Partners are location-mapped in the office-overhead spread

Operator ask: employees were location-tagged (v0.3.98), but partners
weren't — so when the operator narrowed an MIS to a location, ALL
partners still counted as office-overhead recipient heads. Now each
**partner cost centre carries a location** too, and the overhead spread
counts only the partners of the selected location(s).

* **Master Data ▸ Cost Centres** gains a **Location** dropdown (migration
  19 adds ``cost_centres.location_id``; "(none)" = untagged).
* **Overhead recipients are location-filtered** — mirroring the STRICT
  employee filter (v0.3.101). With locations selected, only partners of
  those locations are recipient heads; the pool is spread over that
  smaller set (each remaining head gets a larger per-head share). An
  **untagged** partner (location NULL) is dropped whenever a filter is
  active and **named in a Cover warning** ("N partner(s) with NO location
  assigned were left out of the office-overhead recipients… Assign
  locations in Master Data ▸ Cost Centres"); a **wrong-location** partner
  is dropped silently (the filter doing its job). With no filter (all
  locations) every active partner still counts — behaviour unchanged.
* **Firm total is invariant** — the pool is redistributed and backed out
  by the Office offset exactly, so excluding a partner as a *recipient*
  only reallocates the pool across the remaining heads; the firm's Net is
  identical whatever the selection. Partner P&L columns are NOT hidden by
  location (their revenue/costs are real regardless) — only the overhead
  recipient set changes. The Employee Register roster shows each partner's
  location, and its formula-driven Overhead Recipients COUNTIFS follows
  automatically.

Verified end-to-end: a Mumbai-only run counts only the Mumbai partners
(pool ÷ 3 = 1 Mumbai employee + 2 Mumbai partners), the untagged partner
is named in the warning while the wrong-location one is not, the firm
total_profit is identical across all four location selections
(none / Mumbai / Bangalore / both), the generated workbook's roster
carries only the selected-location Partner rows with their location, and
the Employee Register's Overhead Recipients / per-head cells
formula-evaluate to the strict figures (3 heads, ₹4,000/head).

### v0.3.103 — Period-labeled total columns; Client Billing cumulative column

Two operator follow-ups on the v0.3.102 cumulative feature:

**1. Total columns carry the period, not the partner's initials.** On
the Partner-Manager P&L the partner's total column was labeled with the
partner CODE (collapsed blocks) or "Total" (manager blocks) — beside the
cumulative "Apr-26 to Jun-26" it read as initials + months. The
partner's name already sits in the merged super-header, so the total
columns now carry the CURRENT period label: a July MIS shows
**"Jul-26" | "Apr-26 to Jun-26"** under each partner name (and the same
pair under "MIS Total"). Self / manager sub-columns keep their codes —
they're breakdown labels, not periods.

**2. Client Billing — cumulative column.** New **"Cum <FY window>"**
column right after Grand Total: each client's billing over the FY months
before the selected period, as a live SUMIFS over the "Revenue (FY)"
data sheet (client names are written identically on both sheets, so the
criterion always matches). Clients billed only in the prior window still
get a row (0 current), so the cumulative total never undercounts. The
Grand Total keeps summing ONLY the current period columns.

Verified with the formula evaluator: a May-26 MIS shows per-partner
column pairs "May-26"/"Apr-26" with the right figures; Client Billing
shows PM Client 50,000 current / 1,40,000 cumulative and AM Client
listed with 0 current / 3,50,000 cumulative (TOTAL cum 4,90,000);
partner initials / "Total" no longer appear as column labels; the full
regression suite is green.

### v0.3.102 — Partner-Manager P&L: FY-cumulative column

Operator ask: alongside the selected period's figures, show the
CUMULATIVE figures of the financial-year months before it. MIS for
Jul-26 → a column "Apr-26 to Jun-26" beside the Jul-26 figures; MIS for
Nov-26..Feb-27 → "Apr-26 to Oct-26". Edge case: a selection starting in
April has no prior FY months, so the column shows the WHOLE previous FY
("Apr-25 to Mar-26").

* **Window** — from the FY start (April) of the EARLIEST selected month
  up to the month before it (``_fy_prior_periods``).
* **Formula-driven** — the prior window is computed with the same calc
  engine and written to five ``" (FY)"`` data sheets (Revenue, Expenses,
  Salary, Reimbursements, Provisions); the cumulative column is live
  partner-level SUMIFS over them, sharing one formula builder
  (``_pm_leaf_formula`` / ``_pm_col_arith``) with the comparison sheet.
* **Layout** — every partner block ends with the cumulative column
  (after the partner's Total), and the MIS Total block gains a matching
  cumulative column; %s recompute within the cumulative column so they
  are true YTD ratios. The cumulative column is context only — it is
  NOT summed into the partner Total or MIS Total (the per-partner
  subtotal now sums only the leaf Self/manager columns explicitly, and
  the MIS row references each block's Total column by role).
* **Completeness** — a partner with prior-FY activity but nothing in
  the current period still gets a block (0 current + cumulative), so
  the MIS cumulative never undercounts the firm's year-to-date.

Verified end-to-end with the formula evaluator: window arithmetic
(Jul→Apr-Jun; Nov-Feb→Apr-Oct; Apr→whole previous FY; Jan year
rollover); a May-26 MIS shows PM current 50,000 with cumulative
1,40,000 and pulls in AM (no May activity) with cumulative 3,50,000;
the MIS cumulative Net ties to the April calc run; the partner Total
provably EXCLUDES the cumulative column; an April MIS shows the empty
previous FY as 0 with the current MIS intact; full regression suite
green.

### v0.3.101 — Location filter is now STRICT

Operator ask: when locations are selected before generating, ONLY
employees marked with those locations count in the Employee Register and
the overhead computation. Previously an employee with NO location
assigned was still included (a lenient default so untagged records
wouldn't vanish); now they are excluded whenever the operator narrows
the selection — and the Cover carries a warning naming them ("N
employee(s) with NO location assigned were left out… Assign locations in
Master Data ▸ Employees"), so nothing drops silently. Unresolved raw
timesheet names (no master row yet) are likewise excluded, with the same
warning pointing at Review & Map. With every location ticked (no filter)
behaviour is unchanged — everyone counts. Wrong-location exclusions are
NOT warned about; that's the filter doing its job. Salary and voucher
figures remain unfiltered, and the firm total is identical whatever the
selection (an excluded office-home employee's pay simply stays on Office
instead of joining the pool).

Verified: Mumbai-only run considers only the Mumbai-tagged employee
(pool ÷ 9 = Mumbai employee + 8 partners), the untagged employee is
named in the warning while wrong-location ones are not, the ER sheet's
formula-driven Recipients/Office-Staff-Salary evaluate to the strict
figures, and the full regression suite is green.

### v0.3.100 — Readable month labels throughout the generated MIS

Operator ask: months should read "Apr-26", not "2026-04", everywhere in
the generated MIS; and the PM P&L comparison sheet's column headers
should show the actual periods instead of "Current" / "Comparison".

* **One canonical formatter** — ``util.month_label`` ("2026-04" →
  "Apr-26") and ``util.periods_label`` (one month → "Apr-26"; a
  contiguous run → "Apr-25 to Jul-25"; otherwise a comma list).
  ``report._month_short`` now delegates to it.
* **Every sheet converted**: Cover (reporting/comparison periods), the
  Excel Dashboard subtitle, Cost Centre P&L / Partner-Manager P&L
  subtitles, Budget vs Monthly Sales month headers, Client Billing
  month headers, the Period columns on the Salary / Expenses /
  Reimbursements / Provisions data sheets, the Employee Register
  (summary, prev-month, roster, headcount block, notes), the Client
  Register, the Comparatives sheet headers, calc warnings, and the HTML
  dashboard (already short labels; its provisions "Booked" column and
  header line included).
* **PM P&L (Cmp) headers** are now the period labels themselves —
  e.g. "May-26 | Apr-26 | Δ" (or "Apr-25 to Jul-25" for a range).
* **Cross-sheet formulas stay intact by construction**: the Employee
  Register's SUMIFS/COUNTIFS match Period cells on the Salary /
  Expenses sheets and its own roster, so BOTH sides now render through
  the same formatter — mixing raw and pretty labels would break them,
  which is why the formatter lives in one place.

Verified: a swept comparative workbook contains **zero** raw ``YYYY-MM``
cells across all 22 sheets; Cover / Budget / ER / (Cmp) headers show the
new labels; a multi-month run shows "Apr-26 to May-26"; and the entire
regression suite (locations, overhead, managers, comparison figures,
migrations, UI smoke) passes with the labels in place.

### v0.3.99 — PM P&L comparison side-by-side, location everywhere, Cover formula-driven

Operator feedback on v0.3.98, plus a full sweep for anywhere location was
still missing:

**1. "Partner-Manager P&L (Cmp)" is now a real comparison.** The v0.3.98
edition showed the comparison period standalone, so the operator saw "no
comparison figures". Rebuilt: the same P&L lines with, per partner,
three side-by-side columns — **Current | Comparison | Δ** — plus a
three-column MIS Total block. Current columns SUMIFS the live data
sheets, Comparison columns the " (Cmp)" data sheets, Δ = Current −
Comparison (percentage-point difference on the % rows). Partner-level;
the current period's manager breakdown stays on the main PM P&L sheet.

**2. Location flows everywhere an employee is created or shown.**
* **Review & Map ▸ Resolve Employee** — the create-new-employee form now
  asks for **Location** (dropdown; "(none)" = always included);
  ``resolution.create_employee`` takes ``location_id``.
* **Employee Register** — the roster gains a **Location** column
  (Period | Employee | Home CC | Location | Status | Movement); every
  COUNTIFS (summary, recipients, headcount-by-CC) repointed to the
  shifted Status/Movement columns. Partners show "—".
* **Salary sheet** — new **Location** column (N) so the operator can see
  and filter exactly whose rows fed the pool.
* The overhead computation itself was already location-filtered in
  v0.3.98 (roster, pool, recipients).

**3. Cover totals formula-driven.** Total revenue / Total cost / Net
profit on the Cover were baked strings; they now reference the Cost
Centre P&L total row (``_link_cover``), so the Cover stays true when a
data row is edited.

Verified end-to-end with the formula evaluator: the comparison sheet's
Current/Comparison/Δ evaluate correctly on a two-month scenario (May
50,000 vs April 1,40,000 → Δ −90,000; MIS Net ties to each period's calc
engine run); Cover formulas tie to calc; the roster Location column and
Salary Location column carry the right names; Resolve-Employee dialog
saves the location; all v0.3.97/98 regressions green (managers fold,
location filter, overhead math, migrations, dashboard, UI smoke).

### v0.3.98 — Locations master, partners in the overhead spread, fully formula-driven Employee Register, comparative Partner-Manager P&L

Four operator asks in one release (migration 18):

**1. Locations master + per-location MIS.** New Master Data tab
**Locations** (the offices the firm operates from); the Employee master
gains a **Location** dropdown. The Generate page now offers a location
checklist (hidden until locations exist; all ticked by default): only
employees of the selected locations enter the **Employee Register** and
the **office-overhead computation**. Employees with **no location
assigned are always included** (nothing silently vanishes), and salary /
voucher **figures are never filtered** — an excluded office-home
employee's pay simply stays on Office instead of joining the pool, so
the firm total is identical whatever the selection (verified). The Cover
sheet shows "Locations considered"; a warning note spells out the
filter. The comparison-period run uses the same selection.

**2. Partners are overhead recipients.** Partners aren't in the employee
master, but each **active partner cost centre now counts as one head**
in the overhead spread: Recipients = partner-team active employees +
partners, and each partner CC receives a per-head share (live Salary-
sheet Overhead rows, like employees). Partner rows appear in the ER
roster with status **Partner** (they don't inflate the Active-employee
counts or headcount-by-CC).

**3. Employee Register fully formula-driven.** Two columns were baked
values; now: **Office Staff Salary** = SUMIFS over the Salary sheet's
new **Pool Source** column (Yes on the salary rows of office-home staff
within the selected locations — the range is bounded to the salary-only
rows because the Overhead rows chain back to this sheet, which would
otherwise be a circular reference), and **Overhead Recipients** =
COUNTIFS over the roster (Active minus office-home Active, plus Partner
rows). The whole overhead cascade — pool → per-head → Salary-sheet
Overhead rows → P&Ls — now recomputes live from an edited cell.

**4. Comparative Partner-Manager P&L.** A comparative MIS now carries a
full **"Partner-Manager P&L (Cmp)"** sheet (same matrix layout, built
from the comparison period's own facts), driven by the (Cmp) data
sheets — including a new **Provisions (Cmp)** sheet so its Provisions
row resolves.

Verified end-to-end with the formula evaluator (validated against the
calc engine): pool = office indirect + office staff salary and per-head
share exact (28,000 ÷ 11 heads); location filter drops the excluded
employees from the register and pool while their salary stays put and
the firm Net is IDENTICAL filtered vs unfiltered; ER's G/H cells
evaluate to the filtered figures; the comparative PM P&L ties to the
compare-period calc; migrations idempotent; managers regression green.

### v0.3.97 — Deactivating a manager hides it from the MIS (folds into the partner total)

Operator report: after deactivating all managers in the masters, the
generated MIS still showed a per-manager breakdown. Data is captured with
the `Partner – Manager` string, but a **deactivated** manager means "don't
break the report down by this manager any more — just show the partner
total (which still includes that manager's work)".

The fix lives in **one choke point in the calc engine**
(`calc._mgr_folder`): an inactive manager's id is folded to `None` on every
fact — revenue, expense, labour and reimbursement — at report-build time.
The stored data (voucher splits, employee→manager links) is untouched, so
re-activating the manager brings the breakdown straight back. Because the
Excel P&L, all data sheets and the HTML dashboard read those facts, they
all collapse consistently.

* **Partner-Manager P&L** — a manager whose master row is deactivated no
  longer gets its own sub-column; its figures fold into the partner's own
  ("Self") column. A partner left with **no active managers** collapses to a
  single partner-total column (via `_build_pm_matrix` roles: `self` /
  `manager` / `subtotal` / `partner_total`) instead of an identical
  Self + Total pair. Partners that still have active managers keep their
  full breakdown, so a mixed setup (some managers on, some off) works too.
* **Data sheets** (Revenue / Expenses / Salary / Reimbursements) — the
  Manager column now reads `(unassigned)` for a folded manager, matching
  the SUMIFS the P&L uses.
* **HTML dashboard** — the Partner-Manager section folds the same way; a
  partner with no manager reads as just the partner code (e.g. `PM`) rather
  than `PM – (unassigned)`.

Verified end-to-end with a formula-evaluated tie-out (a mini Excel
evaluator validated against the calc engine): with managers active, all
deactivated, or mixed, **every partner Net and the firm Net are identical**
— only the column breakdown changes. Deactivated managers' figures stay in
the partner total; nothing is lost. Data-sheet Manager columns blank out
and the comparison-period workbook + dashboard still build cleanly.

### v0.3.96 — Cost Centre P&L now mirrors the Partner-Manager P&L heads

The Cost Centre P&L had a coarser column set than the Partner-Manager
P&L. It now carries the SAME line heads (as columns): **Revenue |
Reimbursements (OPE) | Total Income | Salary (billable) | Salary
(non-billable) | Professional Fees | Reimbursement Expenses | Provisions
| Total Direct Costs | Gross Profit | Gross Profit % | Office Overhead |
Indirect Expenses | Net Profit | Net Profit %**. So Salary is split
billable / non-billable, Direct Expense is split into Professional Fees /
Indirect Expenses / Provisions, and Gross Profit / Gross % are added.
Gross/Net % are on sales income (Revenue), matching the PM P&L; Net
Profit equals the previous "Profit" (firm total unchanged — indirect just
moves below the gross line, as in the PM P&L).

Consumers repointed via the sheet's ``rows_pl`` map: the Excel Dashboard
tiles (Total Cost = Total Income − Net Profit, since there's no single
Total-Cost column now) and the Comparatives sheet (current Revenue =
Total Income, Profit = Net Profit). Filtered subtotal-on-top + AutoFilter
cover all 15 amount columns. The HTML dashboard's cost-centre view is
unchanged (a valid coarser summary; its profit/margin already tie).

Verified end-to-end: every column formula, full tie-out to the calc
engine (Net = firm profit), the two % columns on revenue, the total row,
the dashboard tiles and the comparison-period sheet.

### v0.3.95 — Reimbursements sheet: add Manager column

The Reimbursements sheet now shows the employee's **Manager** (from the
employee master) after Employee CC. Amount shifts to col I; the Cost
Centre P&L / Partner-Manager P&L reimbursement SUMIFS were repointed to
the new Amount column. Verified the column populates and totals still tie.

### v0.3.94 — Review & Map ▸ Vouchers: Delete action

Each voucher row in the Review & Map Vouchers tab now has a **Delete**
button (alongside "Edit splits →"), matching the Clients / Employees /
Cost Centres tabs. It confirms, then permanently removes the voucher; its
splits cascade via the FK. New ``vouchers.delete_voucher`` service.

### v0.3.93 — Partner-Manager P&L: Net Profit / Net % now fill the manager columns

The Net Profit and Net Profit % rows were blank (0) in the per-manager
columns — they'd been lumped with Office Overhead (which genuinely can't
split by manager) and hard-coded to 0. Net CAN break down: each manager
column now shows **Net = Gross − Overhead − Indirect** (overhead is 0 in
manager columns, so effectively Gross − Indirect) and **Net % = Net ÷
Sales**. Office overhead stays partner-level and is deducted in the
partner Total column only; a footnote explains the manager Net is before
office overhead. Verified the manager columns now carry live formulas.

### v0.3.92 — Total Income column, sales-based %, filtered subtotals on top

1. **Cost Centre P&L — Total Income column.** New "Total Income" column
   (= Revenue + Reimbursements (OPE)). Profit is now Total Income − Total
   Cost; Profit % is Profit ÷ **Revenue** (sales income only, excluding the
   reimbursement recovery). Mirrored in the dashboard CC table; the Excel
   Dashboard tiles and Comparatives sheet were repointed to the shifted
   columns.
2. **Partner-Manager P&L — Gross/Net % on sales.** Both percentages now
   divide by Sales (Income), not Total Income, at every level (per-manager
   total, partner total, MIS total).
3. **Filtered subtotals on top of every table.** Each amount column now
   carries a ``=SUBTOTAL(109,…)`` cell above the header, and the table is
   an AutoFilter — so when the operator filters, that top cell shows the
   live sum of the visible rows. Applied to the data sheets (Revenue,
   Expenses, Salary, Reimbursements, Provisions — header moved to row 2,
   data to row 3 via a shared ``_DATA_FIRST_ROW``) and the summary sheets
   (Cost Centre P&L, Entity, Service, Budget, Client Billing,
   Comparatives). The bottom TOTAL rows stay plain SUMs. Full-column
   SUMIFS are unaffected because their criteria columns are text (the
   subtotal/header rows never match a criterion).

Verified end-to-end: Total Income / Profit / Profit % formulas, PM
gross/net % denominators, subtotal rows + autofilters on data and summary
sheets, the Salary sheet's live overhead formulas still align after the
row shift, and a comparison-period workbook + dashboard render cleanly.

### v0.3.91 — Reimbursements sheet: add Employee CC column

The Reimbursements sheet now shows the **employee's own cost centre**
("Employee CC", from the employee master) next to the existing booking
``CostCentre`` (the client's partner who bears the cost). The two differ
when an employee of one partner incurs a reimbursement for another
partner's client. New column inserted after Employee (Amount shifts to
col H); the Cost Centre P&L / Partner-Manager P&L SUMIFS that book
reimbursements were updated to the new Amount column. Verified the
columns and that the partner totals still tie.

### v0.3.90 — Reimbursements: make imports idempotent (kill duplicate rows)

Follow-up to the v0.3.89 Grand-Total fix. Reimbursements had **no
de-duplication at all** (unlike vouchers, which dedup by vch_no), so any
double-read produced duplicate rows in the generated Reimbursements sheet
and doubled the cost — e.g. "Aarav Sarda" appearing twice. Causes: the
reference pivots ship the SAME employees in two side-by-side blocks, and
re-importing a reimbursement file simply appended everything again.

* **commit.py** — reimbursement import is now idempotent: an identical
  ``(period, employee, client, amount)`` row already in the DB, or repeated
  within the same file, is skipped (counted under "skipped duplicates").
* **Migration 17** — de-duplicates reimbursement rows already imported
  before this guard, keeping the earliest of each identical group.

Verified: importing the same reimbursement data twice inserts 0 rows the
second time (Aarav stays at one row); the migration collapses planted
duplicates to one while leaving distinct employees untouched.

### v0.3.89 — Budget sales-only, reimbursement double-count, CC P&L bifurcation, residual billable

Five operator-reported changes, reflected in **both** the Excel workbook and the HTML dashboard:

1. **Budget vs Monthly Sales = sales only.** `budget_monthly_data` now groups by service and keeps
   only the **Income** category, excluding Reimbursement/OPE recoveries that also flow through the
   Sales Register.
2. **Manual entries on Dashboard & Cover — confirmed working.** Manual rows persist to the same
   tables → `compute()` totals → Cover figures + the formula-linked Dashboard tiles. Verified with a
   test (a manual sale shows up in Total Revenue).
3. **Reimbursement double-count fixed.** Flat exports end with a pivot **"Grand Total"** row that the
   importer was reading as a real employee (e.g. `Reimb MAy 26.xlsx` → ₹4,82,590 vs real ₹2,41,295).
   New `_is_total_name` guard skips Total/Grand Total/Subtotal rows in the reimbursement, salary and
   timesheet parsers; **migration 16** deletes any such rows already imported. (Individual entries were
   verified NOT doubled — only the pivot total row was.)
4. **Cost Centre P&L bifurcated; Target/Variance removed.** Revenue → `Revenue` (sales income) +
   `Reimbursements (OPE)` (recovery); Direct Expense → `Direct Expense` (vouchers + provisions) +
   `Reimbursements` (reimbursement-sheet outlays). `CostCentreLine` split accordingly with a canonical
   `calc.revenue_category` (the Revenue-sheet Category column delegates to it). Profit/Total Cost
   unchanged (presentation only); Margin % = Profit ÷ (Revenue + Reimb OPE). Excel Dashboard tiles,
   Comparatives, and the dashboard CC table/cost-composition updated to match.
5. **Residual / unallocated salary time is now billable.** The residual labour facts flip to billable
   (except office-home staff), so the Partner-Manager P&L Salary (billable) and the dashboard
   cost-composition reflect it.

Verified end-to-end on a scenario covering all five: firm totals tie, budget excludes OPE, the
reimbursement Grand Total no longer doubles, the CC P&L columns are correct in Excel + dashboard, and
the comparison-period workbook + headless dashboard render cleanly.

### v0.3.88 — Client Register: additions only, no "lost"

Refined the v0.3.87 Client Register per operator feedback: clients bill
irregularly, so a month's absence does NOT mean the client is lost. The
"Lost" concept is removed everywhere. **New** now means billed for the
**first time ever** (MIN billing month across ALL history the system
holds), not just vs the previous month — so a returning client is never
re-flagged, and there's no prev-month dependency.

* **calc** — ``_build_client_register`` computes each client's first-ever
  billing month from the full voucher history; a client is New only in
  that month. No exits/lost.
* **Excel** "Client Register" — columns now Period / Active / New (and
  the by-cost-centre block Active / New); the roster drops Status/Lost.
* **Dashboard** — the movement chart shows Active + New only; table drops
  Lost.

Verified: a client billed last month but not this simply doesn't appear
in this month's list (never "lost"); a returning client isn't flagged
New; first-time clients are. Single- and multi-period runs both correct.

### v0.3.87 — Client Register (Excel + dashboard)

A client analogue of the Employee Register, in both views. Per period it
shows the clients **billed** (appeared on a sales voucher), **new**
clients (first billed this period vs the previous calendar month) and
**lost** clients (billed last month, not this), grouped by the client's
cost centre.

* **calc** ``_build_client_register`` — distinct billed clients per
  period; new/lost compare against the previous month read straight from
  the DB (like the employee register's joiners/exits), so it works even
  when last month isn't a selected period.
* **Excel** "Client Register" sheet — summary (Active / New / Lost via
  COUNTIFS over a per-(period, client) roster), the roster itself, and a
  "Clients by cost centre" breakdown beside it.
* **Dashboard** "Client Register" section — client movement by period,
  active clients by cost centre (stacked), and a by-period table.

Verified end-to-end on a churn scenario (a client billed last month but
not this drops to Lost; a first-time client shows as New), with the
cost-centre grouping correct in both views.

### v0.3.86 — Fix cross-partner manager (e.g. "UV - AM" showing under JV)

A manager record is partner-specific, but a CC string like
"Jalpesh - Umesh" was resolving partner JV and then — when no "Umesh"
existed under JV — falling back to a GLOBAL manager match that grabbed
"UV - AM" (Umesh under AM). That pinned "UV - AM" as a column under JV in
the Partner-Manager P&L.

* **Matcher** (``_match_mgr``): when the partner is resolved, the manager
  is matched ONLY against that partner's team — no global fallback. So
  "Jalpesh - Umesh" → JV with no manager; "Aakash - Umesh" → AM + UV-AM.
  The per-partner "Gaurav" disambiguation is unchanged.
* **Migration 15** cleans data already saved with the bug: any CC-string
  mapping or voucher split whose manager doesn't belong to its cost
  centre has the manager cleared (it drops to the partner's own column);
  re-matching reassigns correctly within the right partner.

Verified: cross-partner strings no longer attach a foreign manager,
same-partner and ambiguous-name matches still resolve, the migration
clears planted mismatches, and the PM matrix shows "UV - AM" only under
AM.

### v0.3.85 — Partner-Manager P&L: salary now breaks down by manager

The salary rows in the Partner-Manager P&L only ever filled the partner's
"Self" column — labour facts didn't carry a manager, so salary couldn't
break down by manager even after employees were mapped to managers +
cost centres in the masters.

Now each labour fact carries the **employee's manager** (from the master),
guarded so a manager only appears under their own partner block — the
manager's home cost centre must equal the cost centre the labour is
charged to; cross-partner billable work still falls to that partner's
Self column. The Salary sheet gained a **Manager** column (L), and the
Partner-Manager P&L's Salary (billable) / Salary (non-billable) rows now
SUMIFS by cost centre **+ manager** per cell, so each manager sub-column
shows its team's labour cost and the partner Total sums them. Employees
with no manager assigned fall under the partner's Self column.

Office overhead stays partner-level (unchanged). Verified end-to-end:
a manager's employees' billable/non-billable salary lands under that
manager's column, an unassigned employee under Self, totals tie to the
Cost Centre P&L, and the comparison-period sheet still builds.

### v0.3.84 — Manual Entry page; fix Clients-tab delete

**Manual Entry (new page + ``manual_entry`` service).** For the one-off
row where uploading a file is overkill, the operator can now add a single
voucher, salary row or reimbursement by hand. Entries land in the SAME
tables the importer writes (``vouchers``/``voucher_splits``,
``salary_entries``, ``reimbursements``) under a "(manual entry)" batch, so
the MIS / dashboard pick them up with no special handling, and masters are
chosen from dropdowns so the rows are already resolved (no Review step).

Fields (\* = required):
* **Voucher** — Type (Sales/Expense)\*, Date\*, Cost centre\*, Amount
  (net)\*; optional Tax, Type-of-Expense (for expense), Party, Client,
  Manager, Service, Voucher no (auto-generated if blank), Description.
* **Salary** — Month\*, Year\*, Employee\*, Cost centre\*, Salary paid\*;
  optional Entity, Category, Reimbursement.
* **Reimbursement** — Month\*, Year\*, Employee\*, Amount\*; optional
  Client, "Client reimbursable" flag.

Saving refreshes Review & Map and Records. (Timesheet stays
upload-only — single daily-log rows aren't a useful manual case.)

**Fix — Review & Map ▸ Clients ▸ Delete did nothing for some names.**
``delete_unmapped_client_rows`` only removed sales vouchers + timesheet
lines, but the Clients queue also surfaces names from **purchase
vouchers** and **reimbursements**. Deleting such a name removed zero rows
so it silently reappeared on reload. Delete now covers all four sources
(sales + purchase vouchers, timesheet, reimbursements); voucher deletes
cascade to their splits. Verified a purchase/reimbursement party now
deletes cleanly with no orphans.

### v0.3.83 — Provision dialogs: separate Month + Year dropdowns

The single month-year list in the Add-provision and Adjust-provision
dialogs is split into two short dropdowns — **Month** (Jan–Dec) and
**Year** (current ±, with any out-of-window year preserved) — so the
operator picks from two short lists instead of one long one. Stored value
is unchanged ('YYYY-MM').

### v0.3.82 — Bare-manager CC strings, Provision Costs, labour reattribution

Three operator requests, all wired through calc → Excel → HTML dashboard.

**1. Bare manager-name CC strings now resolve the manager.** Tally tags
some invoices with just the manager ("Rajesh Malhotra") rather than
"partner – manager". The matcher only tried partners, so it fuzzily (and
coincidentally) landed the right partner but left the manager blank. Now
a bare CC string is also matched against managers; a confident manager
match adopts that manager AND their home partner cost centre (a 100%
manager match beats a weak fuzzy partner match). ``auto_match`` /
``apply_known_cc_string_mappings`` also back-fill the manager on
already-resolved splits/mappings **only when the manager's partner equals
the saved partner**, so existing data upgrades with zero risk of moving a
cost centre. Fixes the blank Manager on the Sales sheet; corrects sales
*and* purchase splits everywhere.

**2. Provision Costs** — a new master tab. A provision is a direct cost a
cost centre EXPECTS to incur for a client but hasn't yet (fields: month,
entity, client, amount). It shows as a direct cost in the MIS and is
**carried forward at its remaining value** in every month from its booked
month onward until cleared. "Adjust provision" records an actual amount +
the month it landed in; the remaining = amount − adjustments up to the
reporting month. New ``provisions`` / ``provision_adjustments`` tables
(migration 14), a ``provisions`` service, calc ``_build_provision_facts``,
a Provisions sheet, and the cost folded into the Cost Centre / Entity /
Partner-Manager P&L direct expense plus a dashboard Provisions section.

**3. Labour reattribution + non-billable split.**
* A partner-team employee's office-booked / non-billable time (client CC
  = Office, or non-billable, or unlogged) now lands on their **home
  partner cost centre**, not Office.
* The Partner-Manager P&L splits salary into **Salary (billable)**
  (client-attributed) and **Salary (non-billable)** via a new Billable
  column on the Salary sheet; the dashboard's cost-composition chart
  splits the same way.
* Employees whose **home CC is Office** are pure overhead: their salary
  joins the overhead pool (office indirect + office-staff salary), which
  is divided across the **partner-team** active employees only (office
  staff are the source, not recipients) and charged to their partner CCs;
  a negative offset on Office keeps the firm total honest. The Employee
  Register summary gained Office Staff Salary / Overhead Recipients /
  Pool columns; the Salary sheet's live overhead formulas chain to them.

Verified end-to-end on synthetic scenarios: bare-manager resolution
(fresh + existing data), provision carry-forward + adjustment across
months, and the labour split — firm totals tie exactly and overhead nets
to zero in every case.

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
