# Bilimoria Mehta & Co. — Automated MIS Generator

A Windows desktop application that turns Tally exports, the staff timesheet and
the salary sheet into a polished, **formula-driven** Management Information
System workbook ready for board meetings.

See [PROJECT.md](PROJECT.md) for the full specification, decisions and design.

---

## What it does

1. **Import** — upload Tally sales/purchase registers, the timesheet and the
   salary & reimbursements sheet. A flexible column-template engine learns each
   file layout once and reuses it.
2. **Review & Map** — resolve unknown clients/employees (fuzzy-matched and
   remembered), and split vouchers across `Partner – Manager` strings.
3. **Master Data** — maintain entities, cost centres, managers, employees,
   clients, services and annual targets — all add/edit/deactivate.
4. **Generate MIS** — pick the month(s), set the reimbursements toggle, then
   export a multi-sheet Excel workbook where every report figure is a live
   formula. Every comparison is worked out for you: beside the reported
   month the Partner-Manager P&L carries the **financial year so far**
   (a Jun-26 MIS shows "Apr-26 to May-26"), and a companion sheet compares
   the **year to date against the same period last year** ("Apr-26 to
   Jun-26" vs "Apr-25 to Jun-25"). Office overhead is computed from the
   books automatically (Office-cost-centre indirect expenses ÷ active
   employees — see the Employee Register sheet).

All history is kept in a local SQLite database, so any period can be
re-reported or compared at any time.

---

## Running from source (development)

```
pip install -r requirements.txt
python run.py
```

Data is stored in a `data/` folder beside the source.

## Building the Windows application

```
pip install pyinstaller
python build.py
```

This produces `dist/BMC MIS/BMC MIS.exe` (a self-contained folder — no Python
needed on the target PC).

## Creating an installer

Install [Inno Setup](https://jrsoftware.org/isinfo.php), then compile
`installer.iss`. It produces `Setup-BMC-MIS.exe` for the accounts head's
computer.

---

## Where data lives

| Mode | Location |
|------|----------|
| From source | `data/` beside the project |
| Installed `.exe` | `%LOCALAPPDATA%\BMC MIS` |
| Override | set the `BMC_MIS_DATA` environment variable |

The folder holds `mis.db` (all historical data) and `exports/` (generated
workbooks). **Back up this folder regularly.**

---

## Tech stack

Python 3.11+ · PySide6 (Qt) · SQLite · openpyxl · rapidfuzz
